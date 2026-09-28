"""Deterministic parser turning Agent Studio's Markdown answers into
ChatResponse-shaped data (ExecutiveAnswer.markdown, QueryData, ChartSpec).

No LLM call is involved here on purpose - see the "Agent Studio As Backend
Plan" decision: the Master/Data/Analysis Agent Backstories already produce
well-formatted Markdown that also needs to render correctly inside Agent
Studio's own chat testing UI, so we adapt that Markdown after the fact
instead of asking the agents to emit machine-readable output or paying for
a second LLM call to reformat it.

This module used to also try to extract a "summary"/"drivers"/"caveats"
breakdown by pattern-matching section headings (Ringkasan, Implikasi
Bisnis, Status & Referensi Data, ...). That approach kept breaking on
real output: exact-heading matching missed variant wording, keyword
matching still needed exemptions for mixed technical/business content,
and ordered lists needed separate handling from bullets - a new failure
mode every time Agent Studio's answer shape varied even slightly. It's
been replaced with rendering the Markdown verbatim on the frontend
(react-markdown) instead, which has no heading/list-shape assumptions to
break. Chart extraction (the one thing that genuinely needs structured
data - Recharts can't render a Markdown table) is untouched below.

The heuristics below (chart type from the question's wording, unit_format
from symbols near the first number) are approximate by design - revisit if
they prove unreliable against real usage, not by trying to make them
perfect up front.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.schemas import ChartSeries, ChartSpec, ExecutiveAnswer, QueryData

_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\|?[\s:|-]+\|?$")


@dataclass
class ParsedMarkdownAnswer:
    answer: ExecutiveAnswer
    data: QueryData
    chart_spec: ChartSpec | None


def parse(markdown: str, question: str) -> ParsedMarkdownAnswer:
    # answer.summary is kept non-empty for any caller still reading it
    # (e.g. conversation history titles) but the frontend's Ask AI surface
    # renders answer.markdown verbatim, not this field.
    answer = ExecutiveAnswer(summary=markdown.strip(), drivers=[], recommended_actions=[], caveats=[], markdown=markdown)

    table = _extract_first_table(markdown)
    if table is None:
        return ParsedMarkdownAnswer(answer=answer, data=QueryData(), chart_spec=None)

    columns, rows = table
    unit_format = _guess_unit_format(markdown)
    data = QueryData(columns=columns, rows=rows, unit_format=unit_format)
    chart_spec = _build_chart_spec(columns, rows, question, unit_format)
    return ParsedMarkdownAnswer(answer=answer, data=data, chart_spec=chart_spec)


def _strip_markdown_emphasis(text: str) -> str:
    return re.sub(r"\*\*(.*?)\*\*", r"\1", text).strip()


def _extract_first_table(markdown: str) -> tuple[list[str], list[dict[str, object]]] | None:
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if not _TABLE_ROW_RE.match(line):
            continue
        header_cells = _split_row(line)
        if index + 1 >= len(lines) or not _TABLE_SEPARATOR_RE.match(lines[index + 1]):
            continue
        rows: list[dict[str, object]] = []
        for data_line in lines[index + 2 :]:
            if not _TABLE_ROW_RE.match(data_line):
                break
            cells = _split_row(data_line)
            row = {
                header_cells[i]: _coerce_cell(cells[i])
                for i in range(min(len(header_cells), len(cells)))
            }
            rows.append(row)
        if rows:
            return header_cells, rows
    return None


def _split_row(line: str) -> list[str]:
    inner = line.strip().strip("|")
    return [_strip_markdown_emphasis(cell.strip()) for cell in inner.split("|")]


_NUMBER_RE = re.compile(r"^-?[\d.,]+%?$")


def _coerce_cell(cell: str) -> object:
    """Numbers in this Backstory's tables use Indonesian formatting
    (Rp 1.371.960.298.317 - '.' as thousands separator, no decimals seen in
    practice). Strip currency/percent symbols and thousands separators; on
    ambiguity (e.g. a lone '.' that could be a decimal point) prefer
    treating '.' as a thousands separator to match observed output, and
    fall back to the original string if the result isn't purely numeric.
    """
    stripped = cell.replace("Rp", "").replace("%", "").strip()
    if not _NUMBER_RE.match(stripped.replace(" ", "")):
        return cell
    normalized = stripped.replace(".", "").replace(",", ".")
    try:
        value = float(normalized)
    except ValueError:
        return cell
    return int(value) if value.is_integer() else value


_PIE_KEYWORDS = ("share", "persentase", "distribusi", "proporsi", "kontribusi")
_LINE_KEYWORDS = ("tren", "trend", "per bulan", "bulanan", "over time")
_BAR_KEYWORDS = ("top", "terbesar", "ranking", "tertinggi", "terendah", "bandingkan")


def _guess_chart_type(question: str) -> str:
    lowered = question.lower()
    if any(keyword in lowered for keyword in _PIE_KEYWORDS):
        return "pie"
    if any(keyword in lowered for keyword in _LINE_KEYWORDS):
        return "line"
    return "bar"


def _guess_unit_format(markdown: str) -> str | None:
    if "Rp" in markdown or "IDR" in markdown:
        return "currency_idr"
    if "%" in markdown:
        return "percent"
    return "quantity"


def _build_chart_spec(
    columns: list[str],
    rows: list[dict[str, object]],
    question: str,
    unit_format: str | None,
) -> ChartSpec | None:
    if len(columns) < 2 or not rows:
        return None
    x_column, *value_columns = columns
    numeric_columns = [
        col for col in value_columns
        if all(isinstance(row.get(col), (int, float)) for row in rows)
    ]
    if not numeric_columns:
        return None
    x_values = [str(row.get(x_column, "")) for row in rows]
    series = [
        ChartSeries(name=col, data=[row.get(col) for row in rows])
        for col in numeric_columns
    ]
    return ChartSpec(
        type=_guess_chart_type(question),
        title=question.strip() or x_column,
        x=x_values,
        series=series,
        unit_format=unit_format,
    )
