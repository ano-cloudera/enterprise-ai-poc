# Qwen CAI Analysis Integration

Qwen is an environment-selected analysis provider behind the generic `LLMProvider` interface. Mock mode remains the default and requires no endpoint, token, or network access.

```env
LLM_MODE=remote
QWEN_BASE_URL=https://<qwen-cai-application>/v1
QWEN_MODEL=Qwen3.8-27B-AWQ
QWEN_API_TOKEN=<secret>
QWEN_REQUEST_TIMEOUT_SECONDS=60
QWEN_MAX_RETRIES=1
QWEN_VERIFY_SSL=true
QWEN_DISABLE_THINKING=true
```

Tokens remain backend-only, are wrapped as secret configuration, are never placed in model payloads, and are never logged. An Authorization header is emitted only when the token is non-empty.

The provider sends `POST {QWEN_BASE_URL}/chat/completions`. Its payload contains only:

- the user question and requested language;
- normalized analytical intent;
- the relevant metric and dimension definitions;
- columns and rows returned by the validated query.

It does not contain credentials, environment variables, SQL, stack traces, unrelated history, or the complete semantic repository. Qwen cannot participate in SQL generation or execution.

The response must validate as `summary`, structured evidence-bearing `drivers`, `recommended_actions`, and `caveats`. Markdown-wrapped or embedded JSON is extracted cautiously. Thinking tags are removed. Invalid JSON/schema and retryable transport failures receive at most one retry; subsequent failure returns a deterministic grounded summary without an HTTP 500.

Local CI does not require live CAI access. To test manually after configuring authentication:

```bash
.venv/bin/python scripts/test_qwen_connection.py
```

The helper reports reachability, safe HTTP status, success, and latency without printing the token or authorization header.
