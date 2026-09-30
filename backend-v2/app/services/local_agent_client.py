from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.core.config import Settings


logger = logging.getLogger(__name__)


class LocalAgentError(Exception):
    """Any failure calling the TEMPO Local Agent fallback - always caught by
    the workflow node, never allowed to fail the overall request."""


class LocalAgentClient:
    """Thin client for the separately deployed TEMPO Local Agent REST API
    (reference/tempo-agent-api). Used only as a last-resort fallback when
    our own OSSIE planner reports strategy=unsupported - this system has
    its own independent governed KPI catalog (SQL always comes from a
    registered query_id, never LLM-generated - see that repo's
    tools.py/impala_runner.py), so a successful call here is still a
    governed answer, just from a second, separate catalog that may not
    agree 1:1 with ours. Callers must label the result as exploratory
    rather than presenting it with the same confidence as our own governed
    path.
    """

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = settings.local_agent_base_url.rstrip("/")
        self.timeout = settings.local_agent_timeout_seconds
        self.engine = settings.local_agent_engine
        self.transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    async def query(self, question: str, *, answer_language: str = "id") -> dict[str, Any]:
        if not self.enabled:
            raise LocalAgentError("LOCAL_AGENT_DISABLED")
        body = {
            "request_text": question,
            "engine": self.engine,
            "format": "json",
            "answer_language": answer_language,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(f"{self.base_url}/v1/query", json=body)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise LocalAgentError("TIMEOUT") from exc
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "local_agent_http_error status=%s endpoint=%s",
                exc.response.status_code,
                exc.request.url.path,
            )
            raise LocalAgentError("HTTP_ERROR") from exc
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise LocalAgentError("REQUEST_FAILED") from exc

        status = str(payload.get("status") or "")
        if status in {"refused", "intent_unavailable", "grain_unavailable"} or not payload.get(
            "final_response_markdown"
        ):
            raise LocalAgentError("NO_ANSWER")
        return payload


_HEADING_RE = re.compile(r"^#+\s*", re.MULTILINE)


def markdown_to_plain_answer(markdown: str) -> str:
    """Reduce the local agent's Markdown answer (## Answer / ## Routing
    sections, tables) to the first prose section for direct_answer /
    executive_summary - the routing/candidate table is internal detail our
    own AnalysisOutput schema has no field for, and stays out of the
    business-facing answer text."""
    text = markdown.split("## Routing")[0]
    text = _HEADING_RE.sub("", text).strip()
    # Drop a trailing "---" section divider some responses include.
    text = re.sub(r"\n-{3,}\s*$", "", text).strip()
    return text or markdown.strip()
