"""Deterministic parser turning Agent Studio's Markdown answers into
ChatResponse-shaped data (ExecutiveAnswer, QueryData, ChartSpec).

No LLM call is involved here on purpose - see the "Agent Studio As Backend
Plan" decision: the Master/Data/Analysis Agent Backstories already produce
well-formatted Markdown that also needs to render correctly inside Agent
Studio's own chat testing UI, so we adapt that Markdown after the fact
instead of asking the agents to emit machine-readable output or paying for
a second LLM call to reformat it.

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
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*)$")
# The Master Agent's greeting/general-question answers use numbered lists
# ("1. Stock Tempo: ...") rather than "-"/"*" bullets, observed for the
# five-domain capability list - without matching this too, each numbered
# item gets swallowed into one run-on fallback paragraph instead of
# staying as separate Key Drivers entries.
_ORDERED_LIST_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")

# Substring match (not exact) on a section's heading, since the Analysis
# Agent's Backstory names these sections loosely in practice (observed:
# "Ringkasan", "Implikasi Bisnis", but also "Analisis", "Status &
# Referensi Data" for what's really a caveat section) - matching by
# keyword survives that variation better than an exact-heading set did.
_DRIVER_HEADING_KEYWORDS = ("ringkasan", "implikasi", "analisis", "analysis", "summary", "key driver", "insight")
_CAVEAT_HEADING_KEYWORDS = ("catatan", "caveat", "limitation", "governance", "status")


@dataclass
class ParsedMarkdownAnswer:
    answer: ExecutiveAnswer
    data: QueryData
    chart_spec: ChartSpec | None


def parse(markdown: str, question: str) -> ParsedMarkdownAnswer:
    sections = _split_sections(markdown)
    summary = _extract_summary(sections)
    drivers = _collect_by_heading_keywords(sections, _DRIVER_HEADING_KEYWORDS)
    caveats = _collect_by_heading_keywords(sections, _CAVEAT_HEADING_KEYWORDS)
    if not drivers and not caveats:
        # No section matched any known keyword at all (fully unfamiliar
        # heading style) - fall back to every paragraph after the first
        # one (which _extract_summary already used) and after any table,
        # since the Backstory's answers consistently follow
        # title -> data/table -> analysis -> governance note even when the
        # exact headings vary.
        drivers = _fallback_paragraphs_after_summary(sections, summary)
    answer = ExecutiveAnswer(summary=summary, drivers=drivers, recommended_actions=[], caveats=caveats)

    table = _extract_first_table(markdown)
    if table is None:
        return ParsedMarkdownAnswer(answer=answer, data=QueryData(), chart_spec=None)

    columns, rows = table
    unit_format = _guess_unit_format(markdown)
    data = QueryData(columns=columns, rows=rows, unit_format=unit_format)
    chart_spec = _build_chart_spec(columns, rows, question, unit_format)
    return ParsedMarkdownAnswer(answer=answer, data=data, chart_spec=chart_spec)


def _split_sections(markdown: str) -> list[tuple[str, list[str]]]:
    """Split into (heading_text, following_lines) pairs; "" heading holds
    any lines before the first heading."""
    sections: list[tuple[str, list[str]]] = []
    current_heading = ""
    current_lines: list[str] = []
    for line in markdown.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            sections.append((current_heading, current_lines))
            current_heading = match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    sections.append((current_heading, current_lines))
    return sections


def _extract_summary(sections: list[tuple[str, list[str]]]) -> str:
    for heading, lines in sections:
        text = "\n".join(lines).strip()
        if not text:
            continue
        # First non-empty paragraph anywhere (usually right after the H3
        # title, before any table) - skip pure table/bullet/numbered-list
        # blocks.
        for paragraph in text.split("\n\n"):
            paragraph = paragraph.strip()
            if paragraph and not paragraph.startswith("|") and not _match_list_item(paragraph):
                return _strip_markdown_emphasis(paragraph.split("\n")[0])
    return ""


def _match_list_item(line: str) -> re.Match[str] | None:
    """Matches either a "-"/"*" bullet or a "1."/"1)" numbered list item -
    the Master Agent's own answers (e.g. the five-domain capability list)
    use numbered lists rather than bullets, and without this a numbered
    list gets swallowed into one run-on paragraph by the fallback path
    below instead of staying as separate driver entries."""
    return _BULLET_RE.match(line) or _ORDERED_LIST_RE.match(line)


def _collect_by_heading_keywords(
    sections: list[tuple[str, list[str]]],
    keywords: tuple[str, ...],
) -> list[str]:
    """Excludes purely technical LINES (e.g. "Metric ID: SI-01"), not whole
    sections, because a section like "Status & Referensi Data" can mix a
    genuine governance caveat bullet with a technical reference bullet
    under one heading - observed in real Analysis Agent output."""
    bullets: list[str] = []
    for heading, lines in sections:
        lowered_heading = heading.strip().lower()
        if not lowered_heading or not any(term in lowered_heading for term in keywords):
            continue
        section_bullets = [
            _strip_markdown_emphasis(match.group(1).strip())
            for line in lines
            if (match := _match_list_item(line)) and not _is_technical_reference_line(match.group(1))
        ]
        if section_bullets:
            bullets.extend(section_bullets)
            continue
        for paragraph in "\n".join(lines).strip().split("\n\n"):
            paragraph = paragraph.strip()
            if paragraph and not paragraph.startswith("|") and not _is_technical_reference_line(paragraph):
                bullets.append(_strip_markdown_emphasis(paragraph.replace("\n", " ")))
    return bullets


_TECHNICAL_FIELD_LABEL_RE = re.compile(r"^\**\s*(metric[\s_]?id|source[\s_]?view|referensi\s+data|reference)\s*[:\**]", re.IGNORECASE)


def _is_technical_reference_line(text: str) -> bool:
    """Only matches a leading field-label style line ("**Metric ID:**
    SI-01") - deliberately not a substring check anywhere in the text,
    since a genuine business caveat can naturally contain the word
    "referensi" in prose (e.g. "...digunakan sebagai referensi awal...")
    without being a technical identifier line."""
    return bool(_TECHNICAL_FIELD_LABEL_RE.match(text.strip()))


def _fallback_paragraphs_after_summary(sections: list[tuple[str, list[str]]], summary: str) -> list[str]:
    """Last-resort driver extraction when no heading matched a known
    keyword. Bullet/numbered-list lines are emitted one per entry (not
    joined into the paragraph they sit in) so a numbered capability list
    like "1. Stock Tempo: ... / 2. Sales / Sell-In: ..." stays as separate
    Key Drivers items instead of one run-on paragraph."""
    entries: list[str] = []
    skipped_summary = False
    for _heading, lines in sections:
        text = "\n".join(lines).strip()
        if not text:
            continue
        for paragraph in text.split("\n\n"):
            paragraph = paragraph.strip()
            if not paragraph or paragraph.startswith(("|", ">")):
                continue
            list_lines = paragraph.split("\n")
            if all(_match_list_item(line) for line in list_lines):
                for line in list_lines:
                    match = _match_list_item(line)
                    if match and not _is_technical_reference_line(match.group(1)):
                        entries.append(_strip_markdown_emphasis(match.group(1).strip()))
                continue
            cleaned = _strip_markdown_emphasis(paragraph.replace("\n", " "))
            if not skipped_summary and cleaned == summary:
                skipped_summary = True
                continue
            entries.append(cleaned)
    return entries


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
