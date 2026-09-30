from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.services.local_agent_client import LocalAgentClient, LocalAgentError, markdown_to_plain_answer


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, local_agent_base_url="http://local-agent.internal", **overrides)


def test_client_is_disabled_when_base_url_is_empty() -> None:
    client = LocalAgentClient(Settings(_env_file=None))
    assert client.enabled is False


@pytest.mark.asyncio
async def test_disabled_client_raises_without_making_a_request() -> None:
    client = LocalAgentClient(Settings(_env_file=None))
    with pytest.raises(LocalAgentError):
        await client.query("Berapa gross sales?")


@pytest.mark.asyncio
async def test_successful_query_returns_the_raw_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/query"
        return httpx.Response(
            200,
            json={
                "status": "pareto",
                "resolved_query_ids": ["SI-01@calquarter_material"],
                "final_response_markdown": "## Answer\n\nTop 5 produk...\n\n## Routing\n\n(details)",
            },
        )

    client = LocalAgentClient(_settings(), transport=httpx.MockTransport(handler))
    payload = await client.query("Top 5 produk dengan sell-in tertinggi")

    assert payload["resolved_query_ids"] == ["SI-01@calquarter_material"]


@pytest.mark.asyncio
async def test_refusal_status_raises_local_agent_error_instead_of_returning_a_non_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "intent_unavailable",
                "resolved_query_ids": [],
                "final_response_markdown": "## Answer\n\nI could not match your question...",
            },
        )

    client = LocalAgentClient(_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(LocalAgentError):
        await client.query("Top 5 widgets with flarn coefficient")


@pytest.mark.asyncio
async def test_timeout_raises_local_agent_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = LocalAgentClient(_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(LocalAgentError):
        await client.query("Berapa gross sales?")


@pytest.mark.asyncio
async def test_http_error_raises_local_agent_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "agent_failed"})

    client = LocalAgentClient(_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(LocalAgentError):
        await client.query("Berapa gross sales?")


def test_markdown_to_plain_answer_strips_routing_section_and_headings() -> None:
    markdown = (
        "## Answer\n\nTotal Gross Sell In adalah Rp 3,84 triliun.\n\n"
        "| Gross Bill Val (IDR) |\n|---:|\n| 3.841.865.787.074 |\n---\n\n"
        "## Routing\n\n**Candidates considered**\n\n| # | Measure |\n| --- | --- |\n| 1 | SI-01 |"
    )
    result = markdown_to_plain_answer(markdown)
    assert "Total Gross Sell In" in result
    assert "Routing" not in result
    assert "Candidates considered" not in result


def test_markdown_to_plain_answer_falls_back_to_raw_text_when_no_sections_match() -> None:
    assert markdown_to_plain_answer("Just plain text, no headings at all.") == "Just plain text, no headings at all."
