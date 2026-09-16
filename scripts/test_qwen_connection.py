from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.llm.models import TrustedAnalysisPayload
from app.llm.providers import LLMProviderError, QwenOpenAICompatibleProvider


async def check(debug: bool) -> int:
    settings = get_settings()
    if not settings.qwen_base_url:
        print("Qwen endpoint is not configured. Set QWEN_BASE_URL.")
        return 2
    provider = QwenOpenAICompatibleProvider(settings)
    payload = TrustedAnalysisPayload(
        question="Summarize the trusted connectivity test result.",
        language="en",
        intent={"pattern": "kpi", "metric": "connectivity_test", "dimensions": [], "filters": {}},
        business_context={"metric_definition": {"name": "connectivity_test", "description": "Synthetic connectivity signal."}, "dimension_definitions": {}},
        query_result={"columns": ["value"], "rows": [{"value": 1}]},
    )
    try:
        result = await provider.generate_structured(payload, language="en", trace_id="manual-connectivity-test")
    except LLMProviderError as error:
        if error.code == "auth_required":
            print(f"Qwen endpoint reachable but authentication failed. HTTP status: {error.http_status}.")
        elif error.code == "timeout":
            print("Qwen endpoint request timed out safely.")
        elif error.code == "unavailable":
            print("Qwen endpoint is unavailable from this environment.")
        else:
            print(f"Qwen endpoint returned an unusable response ({error.code}).")
        return 1
    except Exception:
        if debug:
            traceback.print_exc()
        else:
            print("Qwen connectivity check failed safely. Re-run with --debug for local diagnostics.")
        return 1
    telemetry = result.telemetry
    print("Qwen endpoint reachable: yes")
    print(f"HTTP status: {telemetry.http_status}")
    print("Model response success: yes")
    print(f"Latency: {telemetry.latency_ms} ms")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely test the configured Qwen CAI endpoint without printing credentials.")
    parser.add_argument("--debug", action="store_true", help="Print a local traceback for unexpected client errors.")
    args = parser.parse_args()
    return asyncio.run(check(args.debug))


if __name__ == "__main__":
    sys.exit(main())
