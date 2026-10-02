from __future__ import annotations

import asyncio
import logging
import re
from time import perf_counter
import uuid

from app.core.config import Settings
from app.core.models import AnalysisOutput, AskDataRequest, AskDataResponse, ChartSpec, QueryData, Timings
from app.db.base import BackendExecutionContext, DataBackendError
from app.db.impala_backend import ImpalaBackend
from app.graph.workflow import WorkflowDependencies, build_workflow
from app.llm.registry import ProviderRegistry
from app.semantic.context import SemanticContextService
from app.semantic.registry import _normalize as normalize_for_match
from app.services.history import ConversationStore
from app.services.local_agent_client import LocalAgentClient
from app.sql.validator import validate_sql


logger = logging.getLogger(__name__)


def _canonical_clarification_choice(question: str, clarification: str) -> str | None:
    # Substring match on the question (not an exact-set membership check) so
    # a short reply that carries extra filler words around the actual choice
    # - "untuk sell out", "ya sell-in dong", "pilih sell out aja" - still
    # resolves. Dash-insensitive ("sell out" vs "Sell-Out") since users type
    # the unhyphenated form far more often than the question's own wording.
    normalized = re.sub(r"[^a-z0-9]+", " ", question.casefold()).strip()
    # Same folding as registry.resolve_ambiguity() discriminators: "Sell-Out",
    # "sell out", and "sellout" all become the substring "sellout".
    folded = normalize_for_match(question)
    offered = clarification.casefold().replace("–", "-")
    sell_in_phrases = ("sell in", "penjualan tempo ke customer", "penjualan tempo ke pelanggan")
    sell_out_phrases = ("sell out", "penjualan partner ke konsumen", "penjualan partner ke customer")
    if "sell-in" in offered and (
        any(phrase in normalized for phrase in sell_in_phrases) or "sellin" in folded
    ):
        return "sell-in"
    if "sell-out" in offered and (
        any(phrase in normalized for phrase in sell_out_phrases) or "sellout" in folded
    ):
        return "sell-out"
    return None


def contextualize_question(question: str, history: list[dict]) -> str:
    """Resolve a short clarification choice without replaying bulky query rows."""
    normalized = " ".join(question.casefold().replace("–", "-").split())
    # Full standalone questions (typical UAT prompts are 8+ tokens) must
    # never be rewritten from prior-turn analyst prose in the same session.
    if len(normalized.split()) >= 8 or not history:
        return question
    previous = history[-1]
    previous_question = str(previous.get("question") or "").strip()
    previous_answer = previous.get("answer") or {}
    answer_parts = [
        str(previous_answer.get("direct_answer") or ""),
        str(previous_answer.get("executive_summary") or ""),
        " ".join(str(item) for item in previous_answer.get("insights") or []),
    ]
    clarification = " ".join(part for part in answer_parts if part).strip()
    canonical_choice = _canonical_clarification_choice(question, clarification)
    selected_choice = canonical_choice or question.strip()
    choice_tokens = set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", canonical_choice or normalized))
    clarification_tokens = set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", clarification.casefold()))
    # "tempo" is excluded alongside the other filler words - it is the
    # brand name and appears in almost every clarification/question
    # regardless of topic, so its presence is never a real signal that a
    # short new question is actually answering the prior clarification.
    ignored = {"ya", "iya", "betul", "untuk", "data", "yang", "mau", "saya", "the", "a", "tempo"}
    selected_tokens = {token for token in choice_tokens - ignored if len(token) > 2}
    overlap = selected_tokens & clarification_tokens
    offered = clarification.casefold()
    offers_choice = (
        ("sell-in" in offered and "sell-out" in offered)
        or ("dc stock" in offered and "store stock" in offered)
        or ("stok dc" in offered and "stok store" in offered)
        or ("stok gudang tempo" in offered and ("stok dc" in offered or "stok retail" in offered))
        or ("proxy" in offered and "promo" in offered and "metrik mana" in offered)
        or (" atau " in f" {offered} " and "?" in clarification)
    )
    # A single shared token is too weak a signal on its own - long
    # clarification paragraphs (e.g. the ROI-promo proxy explanation) share
    # common domain words ("penjualan", "produk") with completely unrelated
    # follow-up questions purely by coincidence. Require at least two
    # overlapping tokens (or an exact canonical match) before treating a
    # new question as an answer to the old clarification.
    if previous_question and offers_choice and (canonical_choice or len(overlap) >= 2):
        return f"{previous_question}\nKlarifikasi pengguna: {selected_choice}"
    return question


class ImpalaQueryExecutor:
    def __init__(self, settings: Settings) -> None:
        self.backend = ImpalaBackend(settings)

    async def execute(self, sql: str, request_id: str) -> dict:
        result = await asyncio.to_thread(
            self.backend.execute,
            sql,
            BackendExecutionContext(trace_id=request_id, purpose="ask_data_v2"),
        )
        return {
            "columns": [column.name for column in result.columns],
            "rows": result.records(),
            "row_count": result.row_count,
            "execution_ms": result.telemetry.query_latency_ms,
        }


class ChatService:
    def __init__(
        self,
        settings: Settings,
        *,
        dependencies: WorkflowDependencies | None = None,
        history: ConversationStore | None = None,
    ) -> None:
        self.settings = settings
        context = SemanticContextService(settings.project_root / settings.ossie_project_id)
        self.dependencies = dependencies or WorkflowDependencies(
            semantic_context=context,
            provider_registry=ProviderRegistry(settings),
            query_executor=ImpalaQueryExecutor(settings),
            sql_validator=lambda sql, validation_context: validate_sql(sql, validation_context, max_rows=settings.sql_max_rows),
            validation_context=context,
            local_agent_client=LocalAgentClient(settings),
        )
        self.workflow = build_workflow(self.dependencies)
        self.history = history or ConversationStore(settings.conversation_db_path)

    async def run(self, request: AskDataRequest) -> AskDataResponse:
        request_id = str(uuid.uuid4())
        started = perf_counter()
        conversation_history = self.history.load(request.session_id, limit=4)
        initial = {
            **request.model_dump(),
            "original_question": request.question,
            "question": contextualize_question(request.question, conversation_history),
            "conversation_history": [
                {"question": item["question"], "answer": item["answer"]}
                for item in conversation_history
            ],
            "request_id": request_id,
            "retry_count": 0,
            "timings": {},
        }
        try:
            state = await self.workflow.ainvoke(initial)
            answer = AnalysisOutput.model_validate(state["answer"])
            chart = ChartSpec.model_validate(state["chart_spec"]) if state.get("chart_spec") else None
            raw_data = state.get("query_result") or {"columns": [], "rows": [], "row_count": 0, "execution_ms": 0}
            timings = {**state.get("timings", {}), "total_ms": round((perf_counter() - started) * 1000, 3)}
            response = AskDataResponse(
                request_id=request_id,
                session_id=request.session_id,
                status=state.get("status", "ERROR"),
                provider=request.provider,
                model=request.model,
                strategy=state.get("strategy", "unsupported"),
                answer=answer,
                data=QueryData.model_validate(raw_data),
                chart_spec=chart,
                timings=Timings.model_validate(timings),
                retry_count=state.get("retry_count", 0),
            )
            self.history.append(request.session_id, request.question, answer, response.data.rows, chart, request.provider, request.model)
            logger.info(
                "ask_data request_id=%s session_id=%s provider=%s model=%s strategy=%s status=%s retry_count=%s timings=%s",
                request_id, request.session_id, request.provider, request.model, response.strategy, response.status, response.retry_count, response.timings.model_dump_json(),
            )
            return response
        except DataBackendError as exc:
            # The adapter already emitted safe telemetry. Do not attach the
            # chained driver traceback here because HTTP responses can contain
            # infrastructure details that do not belong in application logs.
            logger.warning(
                "ask_data_backend_failed request_id=%s session_id=%s provider=%s model=%s safe_error_code=%s",
                request_id, request.session_id, request.provider, request.model, exc.code,
            )
            elapsed = round((perf_counter() - started) * 1000, 3)
            auth_failed = exc.code == "IMPALA_AUTH_FAILED"
            return AskDataResponse(
                request_id=request_id,
                session_id=request.session_id,
                status="ERROR",
                provider=request.provider,
                model=request.model,
                strategy="unsupported",
                answer=AnalysisOutput(
                    direct_answer=(
                        "Autentikasi ke Impala gagal."
                        if auth_failed
                        else "Query data tidak dapat diselesaikan."
                    ),
                    executive_summary=(
                        "Backend tidak dapat membuka sesi Impala. Hubungi operator aplikasi."
                        if auth_failed
                        else "Backend data mengembalikan kegagalan yang aman. Gunakan request ID untuk penelusuran operator."
                    ),
                    insights=[],
                    business_implications=[],
                    caveats=[
                        "Periksa profil LDAP atau GSSAPI pada environment backend."
                        if auth_failed
                        else "Internal driver details are not exposed."
                    ],
                    data_reference="No result available.",
                    chart_spec=None,
                ),
                data=QueryData(), chart_spec=None, timings=Timings(total_ms=elapsed),
            )
        except Exception:
            logger.exception("ask_data_failed request_id=%s session_id=%s provider=%s model=%s", request_id, request.session_id, request.provider, request.model)
            elapsed = round((perf_counter() - started) * 1000, 3)
            return AskDataResponse(
                request_id=request_id,
                session_id=request.session_id,
                status="ERROR",
                provider=request.provider,
                model=request.model,
                strategy="unsupported",
                answer=AnalysisOutput(
                    direct_answer="Permintaan tidak dapat diselesaikan dengan aman.",
                    executive_summary="Terjadi kesalahan internal. Gunakan request ID untuk penelusuran operator.",
                    insights=[], business_implications=[], caveats=["Internal error details are not exposed."],
                    data_reference="No result available.", chart_spec=None,
                ),
                data=QueryData(), chart_spec=None, timings=Timings(total_ms=elapsed),
            )

    async def stream(self, request: AskDataRequest):
        labels = {
            "understanding_request": "Understanding request",
            "retrieving_context": "Retrieving semantic context",
            "preparing_query": "Preparing governed query",
            "validating_query": "Validating query",
            "querying_data": "Querying TEMPO data",
            "analyzing_result": "Analyzing result",
        }
        for stage, label in labels.items():
            yield {"type": "progress", "stage": stage, "label": label}
        yield {"type": "done", "response": await self.run(request)}
