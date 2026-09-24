from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


def _normalize(value: str) -> str:
    return re.sub(r"[\s_\-.,!?;:'\"/]+", "", value).casefold()


# Words that carry no metric-identifying meaning on their own (Indonesian and
# English function words, plus generic question phrasing) - excluded from
# token-overlap matching in resolve_metric so a short/common word like
# "nilai" or "value" doesn't dominate the score or cause spurious partial
# matches across unrelated metrics.
_STOPWORDS = frozenset({
    "yang", "dengan", "dan", "atau", "untuk", "dari", "pada", "ini", "itu",
    "mana", "apa", "apakah", "bagaimana", "berapa", "adalah", "the", "a",
    "an", "of", "for", "with", "and", "or", "is", "are", "value", "nilai",
    "per", "each", "setiap", "total", "jumlah",
})


def _tokenize(value: str) -> set[str]:
    """Splits into lowercase word tokens (letters/digits only, "sell-in"
    becomes ["sell", "in"]) and drops stopwords - used for word-overlap
    matching, distinct from _normalize's whitespace-stripped exact-substring
    form. A phrase like "nilai Sell-In terbesar" and a synonym like
    "material sell-in value" share {"sell", "in"} either way, but
    tokenization also lets each individual content word be checked for
    membership regardless of the words around it."""
    return {word for word in re.findall(r"[a-z0-9]+", value.casefold()) if word and word not in _STOPWORDS}


class TempoOssieRegistry:
    """Read-only registry for the official-root Apache Ossie model."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir.resolve()
        self.model_path = self.project_dir / "ossie" / "tempo_core.ossie.yaml"
        self.governance_path = self.project_dir / "ossie" / "tempo_governance.yaml"
        self.golden_path = self.project_dir / "ossie" / "golden_questions.yaml"

        self.model = self._load(self.model_path)
        self.governance = self._load(self.governance_path)
        self.golden_questions = self._load(self.golden_path)
        self.datasets = {item["name"]: item for item in self.model.get("datasets", [])}
        self.metrics = {item["name"]: item for item in self.model.get("metrics", [])}
        self.dataset_fields = {
            name: {field["name"]: field for field in dataset.get("fields", [])}
            for name, dataset in self.datasets.items()
        }
        self.metric_configs = {
            name: self.tempo_extension(metric) for name, metric in self.metrics.items()
        }
        self.validate()

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(path)
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Expected YAML object in {path}")
        return value

    @staticmethod
    def tempo_extension(item: dict[str, Any]) -> dict[str, Any]:
        for extension in item.get("custom_extensions", []):
            if extension.get("vendor_name") != "TEMPO":
                continue
            data = extension.get("data", {})
            return json.loads(data) if isinstance(data, str) else dict(data)
        return {}

    @staticmethod
    def ansi_expression(item: dict[str, Any]) -> str:
        expression = item.get("expression", {})
        if isinstance(expression, str):
            return expression
        for candidate in expression.get("dialects", []):
            if candidate.get("dialect") == "ANSI_SQL":
                return str(candidate["expression"])
        raise ValueError(f"No ANSI_SQL expression for {item.get('name')}")

    def validate(self) -> None:
        errors: list[str] = []
        if self.model.get("name") != "tempo_q4_governed":
            errors.append("Unexpected Ossie model name")
        # Minimums, not exact counts: the original Semantic Contract v1 (5
        # datasets / 28 metrics) is the floor. The 24 Sep 2026 journey
        # expansion (Stock Tempo -> Sales -> B2B -> SAT-IDM -> OOS, see
        # TEMPO_DATAMART_PLAN.md §8.1) added 9 more datasets and 13 more
        # metrics on top of that floor - an exact-count check would reject
        # any further intentional growth of the governed model.
        if len(self.datasets) < 5:
            errors.append("TEMPO Impala profile expects at least five datasets")
        if len(self.metrics) < 28:
            errors.append("TEMPO Impala profile expects at least 28 metrics")
        if self.model.get("relationships"):
            errors.append("Runtime joins are disabled for Semantic Contract v1")

        for dataset_name, dataset in self.datasets.items():
            fields = self.dataset_fields[dataset_name]
            for key in dataset.get("primary_key", []):
                if key not in fields:
                    errors.append(f"{dataset_name} primary key references unknown field {key}")

        metric_ids: set[str] = set()
        for metric_name, metric in self.metrics.items():
            config = self.metric_configs[metric_name]
            metric_id = config.get("metric_id")
            dataset_name = config.get("base_dataset")
            if not metric_id:
                errors.append(f"{metric_name} has no metric_id")
            elif metric_id in metric_ids:
                errors.append(f"Duplicate metric_id {metric_id}")
            metric_ids.add(str(metric_id))
            if dataset_name not in self.datasets:
                errors.append(f"{metric_name} has invalid base_dataset {dataset_name}")
                continue
            dimensions = {
                name
                for name, field in self.dataset_fields[dataset_name].items()
                if "dimension" in field
            }
            unknown = set(config.get("allowed_dimensions", [])) - dimensions
            if unknown:
                errors.append(f"{metric_name} has unknown dimensions {sorted(unknown)}")

        if errors:
            raise ValueError("Invalid TEMPO Ossie registry:\n- " + "\n- ".join(errors))

    def metric_aliases(self, metric_name: str) -> list[str]:
        metric = self.metrics[metric_name]
        context = metric.get("ai_context", {})
        values = [metric_name, metric.get("description", "")]
        values.extend(context.get("synonyms", []) if isinstance(context, dict) else [])
        return [str(value) for value in values if value]

    def resolve_ambiguity(self, question: str) -> dict[str, Any] | None:
        normalized = _normalize(question)
        for ambiguity in self.governance.get("ambiguities", []):
            if (
                ambiguity.get("name") == "sales_stage"
                and "salesoffice" in normalized
                and not any(
                    _normalize(term) in normalized
                    for term in ("revenue", "pendapatan", "nilai penjualan", "gross sales")
                )
            ):
                continue
            if not any(
                _normalize(str(term)) in normalized
                for term in ambiguity.get("trigger_terms", [])
            ):
                continue
            selected = []
            for option in ambiguity.get("options", []):
                if any(
                    _normalize(str(term)) in normalized
                    for term in option.get("discriminators", [])
                ):
                    selected.append(option)
            if len(selected) == 1:
                return None
            return {
                "status": "needs_clarification",
                "reason": ambiguity["name"],
                "question": ambiguity["question"],
                "options": ambiguity.get("options", []),
            }
        return None

    def resolve_metric(self, question: str) -> dict[str, Any]:
        ambiguity = self.resolve_ambiguity(question)
        if ambiguity:
            return ambiguity

        normalized = _normalize(question)
        dimension_terms = {
            "material": ("material", "sku", "produk"),
            "customer": ("customer", "pelanggan"),
            "sales_office": ("sales office", "cabang", "office"),
            "fill_rate_band": ("fill rate band", "kategori fill", "low fill"),
            "calmonth": ("bulan", "bulanan", "month", "trend", "tren"),
        }
        hinted_dimensions = {
            dimension
            for dimension, terms in dimension_terms.items()
            if any(_normalize(term) in normalized for term in terms)
        }
        company_scope = any(
            _normalize(term) in normalized
            for term in ("company", "perusahaan", "tempo total", "total tempo")
        )
        # A question with no dimension hint beyond calmonth ("Fill Rate per
        # bulan?", no mention of "material"/"sku"/"produk"/"cabang"/etc.) is
        # most naturally read as asking for the company-wide aggregate, not
        # a specific breakdown - several metrics share generic aliases like
        # "fill rate" (company/material/service-level fill rate all do), so
        # without this the shortest alias wins by token-count alone and a
        # plain, unqualified question resolves to a granular per-material
        # metric instead of the aggregate one golden_questions.yaml expects.
        unqualified_scope = hinted_dimensions <= {"calmonth"}

        question_tokens = _tokenize(question)
        candidates: list[tuple[int, str, str]] = []
        for metric_name in self.metrics:
            config = self.metric_configs[metric_name]
            allowed_dimensions = set(config.get("allowed_dimensions", []))
            dataset_name = config.get("base_dataset")
            for alias in self.metric_aliases(metric_name):
                normalized_alias = _normalize(alias)
                alias_tokens = _tokenize(alias)
                # Two ways an alias can match a question, checked together so
                # neither phrasing style is required: (1) an exact,
                # whitespace-stripped substring match - the strongest signal,
                # since it means the alias's exact wording appears verbatim;
                # (2) every content word (stopwords excluded) in the alias
                # also appears somewhere in the question, in any order - this
                # is what makes phrasing like "nilai Sell-In terbesar" match
                # a synonym written as "material sell-in value" (both reduce
                # to the shared token {"sell", "in"} once stopwords like
                # "nilai"/"value" are dropped), without resorting to an
                # LLM/embedding call for what's meant to stay a deterministic,
                # governed lookup.
                is_substring_match = bool(normalized_alias) and normalized_alias in normalized
                is_token_match = bool(alias_tokens) and alias_tokens <= question_tokens
                if not (is_substring_match or is_token_match):
                    continue
                score = len(normalized_alias) if is_substring_match else len(alias_tokens)
                if not is_substring_match:
                    # Token-overlap matches are inherently less certain than
                    # an exact substring (word order/context is ignored), so
                    # rank every substring match above every token-only match
                    # regardless of alias length.
                    score -= 1000
                score += 100 * len(hinted_dimensions & allowed_dimensions)
                if any(
                    dimension in metric_name
                    for dimension in hinted_dimensions
                ):
                    score += 50
                if company_scope and dataset_name == "monthly_executive":
                    score += 100
                if unqualified_scope and allowed_dimensions <= {"calmonth"}:
                    score += 75
                candidates.append((score, metric_name, alias))
        if not candidates:
            return {
                "status": "unsupported",
                "reason": "no_published_metric_match",
                "question": self.governance.get("unknown_metric_question"),
                "capabilities": self.capability_summary(),
            }
        candidates.sort(reverse=True)
        _, metric_name, alias = candidates[0]
        return {
            "status": "resolved",
            "metric": metric_name,
            "matched_alias": alias,
            "definition": self.metric_definition(metric_name),
        }

    def metric_catalog_for_classification(self) -> list[dict[str, str]]:
        """Closed list of {name, description} for every governed metric, used
        as the candidate set an LLM fallback classifier picks from when the
        deterministic token matcher in resolve_metric() finds no match. Kept
        separate from resolve_metric so the primary path stays a pure,
        LLM-free lookup - this only feeds a downstream fallback, never
        replaces the deterministic result when one exists."""
        return [
            {"name": name, "description": str(metric.get("description") or "")}
            for name, metric in self.metrics.items()
        ]

    def metric_definition(self, metric_name: str) -> dict[str, Any]:
        if metric_name not in self.metrics:
            raise KeyError(metric_name)
        metric = self.metrics[metric_name]
        config = self.metric_configs[metric_name]
        return {
            "name": metric_name,
            "metric_id": config.get("metric_id"),
            "description": metric.get("description"),
            "expression": self.ansi_expression(metric),
            "datatype": metric.get("datatype"),
            "base_dataset": config.get("base_dataset"),
            "allowed_dimensions": config.get("allowed_dimensions", []),
            "required_filters": config.get("required_filters", []),
            "row_filter": config.get("row_filter"),
            "governance_status": config.get("governance_status"),
            "business_approval_status": config.get("business_approval_status"),
            "original_kpi_id": config.get("original_kpi_id"),
            "ai_context": metric.get("ai_context", {}),
        }

    def capability_summary(self) -> dict[str, Any]:
        return {
            "model": self.model["name"],
            "scope": self.governance.get("scope", {}),
            "datasets": [
                {
                    "name": name,
                    "description": dataset.get("description"),
                    "source": dataset.get("source"),
                }
                for name, dataset in self.datasets.items()
            ],
            "metrics": [
                self.metric_definition(metric_name) for metric_name in self.metrics
            ],
            "examples": [
                item["question"]
                for item in self.golden_questions.get("questions", [])
                if item.get("expected_status") in {"supported", "supported_with_caveat"}
            ][:8],
        }

