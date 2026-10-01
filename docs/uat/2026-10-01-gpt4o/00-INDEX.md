# UAT Index — GPT-4o (OpenAI) via backend-v2, live Impala

Run date: 2026-10-01. Provider: `openai` / `gpt-4o`. Backend: full `ChatService` pipeline
(deterministic resolver → governed SQL or LLM query planner → SQL validation → live Impala
execution → GPT-4o result analysis). All answers below are copied verbatim from the model's
own output — not edited or summarized by hand.

| # | Question | Status | Strategy | File |
|---|---|---|---|---|
| 01 | Top 10 produk dengan penjualan terbesar di Tempo | SUCCESS | governed | [01-success.md](01-success.md) |
| 02 | Top 10 cabang/ sales office dengan penjualan terbesar di tempo | SUCCESS | governed | [02-success.md](02-success.md) |
| 03 | Tampilkan stok produk A di cabang A dan hitung bisa meng-cover penjualan berapa hari dari stok tersebut | **UNSTABLE (see note)** | governed | [03-ATTEMPT1-unsupported.md](03-ATTEMPT1-unsupported.md), [03-ATTEMPT2-error.md](03-ATTEMPT2-error.md) |
| 04 | Top 10 produk di B2B dengan penjualan tertinggi | SUCCESS | governed | [04-success.md](04-success.md) |
| 05 | Top 10 DC Alfamart dengan penjualan tertinggi | CLARIFICATION | clarification | [05-clarification.md](05-clarification.md) |
| 06 | Cek stok produk A di toko alfamart dan bandingkan dengan stok di DC | CLARIFICATION | clarification | [06-clarification.md](06-clarification.md) |
| 07 | Hitung promo dengan ROI terbaik dan berikan rekomendasi/ saran | CLARIFICATION | clarification | [07-clarification.md](07-clarification.md) |
| 08 | Hitung service level/ fill rate di cabang tempo dan urutkan SL terjelek | SUCCESS | governed | [08-success.md](08-success.md) |
| 09 | Analisa data unloading dan picking dan berikan Analisa dan perbandingan dengan Industri standard | SUCCESS | sql_fallback | [09-success.md](09-success.md) |

## Notes

**#3 is non-deterministic across runs with GPT-4o**, even at `temperature=0`. Across 4+
attempts the model returned different results for the exact same question and resolver
context: `unsupported`, a SQL attempt with an invalid column reference (using the metric
name as a literal column name), and an empty-SQL validation failure. It never answered
confidently with a wrong number — every attempt failed safely (no answer, or an explicit
validation error) rather than presenting a misleading result. Root cause: the question asks
for a breakdown ("di cabang A") that the resolved governed metric (`months_of_stock_cover`)
genuinely does not support (no branch/sales_office dimension exists for it) - this is a
real gap in governed coverage for this question, not purely a prompt-engineering bug. Two
fixes landed during this UAT round (see PROJECT_STATE.md, 1 Oct 2026): (1) a `resolver_hint`
is now passed to the LLM query planner whenever the deterministic resolver found a strong
candidate metric but couldn't fully match the requested dimensions, which fixed #2 (same
"di cabang" pattern, now consistently SUCCESS) and #9; and (2) the metric's AI-context
instructions were shortened after an initial verbose version appeared to crowd out the
model's attention on required output fields. #3 remains unresolved because the underlying
data gap (no branch-level sell-in-vs-stock metric) is real, not a wording issue.

**#9 required one retry** after the first attempt hit an OpenAI rate limit (`429
rate_limit_exceeded`) from running 4 UAT passes back-to-back in this session — this is an
infrastructure/quota artifact of the testing session, not a product bug. The retry (same
question, fresh session) succeeded cleanly.
