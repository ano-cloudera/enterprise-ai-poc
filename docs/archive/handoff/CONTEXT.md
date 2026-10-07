# Tempo Scan PoC — Full Handoff Context

## Customer & Objective
Customer: PT Tempo Scan Pacific / Tempo Scan.

PoC objective:
- AI assistant untuk Q&A data bisnis, mayoritas tabular
- CDP untuk ingestion, ETL, governance, semantic/business layer
- Cloudera AI untuk LLM serving, reasoning, insight generation, forecasting, dan AI application
- target user: management / executive
- Bahasa Indonesia + English

Timeline:
- target mulai 14 Sept 2026
- final sebelum akhir Sept 2026
- budgeting direncanakan Oktober 2026
- volume data PoC sekitar 5 GB

Asumsi data internal:
- sales
- outlet
- product
- customer
- inventory
- region
- channel
- kemungkinan source SAP BW dan SQL-based sources

Added value:
- forecasting sales per product / region / channel
- external data: weather, competitor pricing/promotion, possible market-share signal
- AI output: answer, insight, chart, recommendation

## Hero Use Case
Tempo Scan Commercial Intelligence Assistant.

Target question:
"Kenapa sales Jawa Barat turun bulan ini?"

Target answer:
- Executive Summary
- Key Drivers
- Recommended Actions
- optional chart / breakdown

Prinsip: AI harus menjawab berdasarkan trusted business data, bukan hanya model memory.

## Target Architecture
Internal Data + External Signals
→ Cloudera Data Platform
→ Ingestion / Curated / Governance / Semantic Layer
→ Cloudera AI
→ LLM + Reasoning + Forecasting
→ Dashboard + Ask AI + Insight + Recommendation

## UI/UX Direction
Brand: Tempo Scan, merah + navy + putih, clean enterprise, management-friendly.

Main features:
1. Dashboard
2. Ask AI
3. Settings
4. AI Monitoring

Dashboard target:
- Net Sales
- Growth
- Inventory Health
- Top Region
- Forecast Next Month
- Sales Trend
- Sales by Region
- Top Product / Channel
- AI insight/chat side panel

Ask AI:
- conversation
- Bahasa Indonesia / English
- executive summary
- key drivers
- recommended actions
- optional chart

Settings:
- model endpoint
- system prompt
- temperature
- max tokens
- thinking toggle

AI Monitoring:
- query count
- latency
- success/failure
- token usage
- model
- timestamp
- user

## Current AI Model
Model: `nicosuter/Qwen3.8-27B-AWQ`

Local path:
`/home/cdsw/models/Qwen3.8-27B-AWQ`

Runtime:
- Cloudera AI
- NVIDIA L40S
- ~46 GB usable VRAM

vLLM:
- 0.29.0

Config:
- max-model-len = 4096
- gpu-memory-utilization = 0.90
- max-num-seqs = 4

CUDA note:
- NVIDIA driver/runtime tersedia
- `nvcc` tidak tersedia
- full CUDA Toolkit tidak tersedia
- FlashInfer sampler pernah gagal karena butuh nvcc

Workaround:
`VLLM_USE_FLASHINFER_SAMPLER=0`

## Current vLLM Deployment
CAI Public URL
→ FastAPI proxy on `CDSW_READONLY_PORT`
→ `127.0.0.1:9000`
→ vLLM
→ Qwen3.8-27B-AWQ
→ L40S

Reason:
- `CDSW_APP_PORT` bentrok dengan service internal CAI
- exposed service pakai `CDSW_READONLY_PORT`
- vLLM tetap internal

Public URL used during dev:
`https://qwen-model.ml-6e4750a0-e43.ano03-cd.a465-9q4k.cloudera.site`

Routes:
- `/`
- `/health`
- `/v1/models`
- `/v1/chat/completions`
- `/v1/completions`

Important startup lesson:
- jangan hanya `sleep(5)`
- model 27B bisa lama load/warmup
- readiness poll ke `http://127.0.0.1:9000/v1/models`
- timeout 900 sec

## Current Gradio UI
Open WebUI dibatalkan karena runtime CAI Python 3.10 sedangkan current Open WebUI butuh Python >=3.11.

Chosen: Gradio 5.49.1.

Requirements:
- gradio==5.49.1
- requests==2.32.5

Current UI:
- horizontal layout
- fixed left settings
- large right chat
- Tempo Scan branding
- endpoint test works
- Qwen response works
- Bahasa Indonesia works
- system prompt editable
- temperature + max tokens
- thinking toggle
- suggested prompts

Latest UI fixes:
- Settings / Chat Conversation title hitam
- chat text putih di dark navy chat area
- Thinking / Reasoning label putih, checkbox clickable
- Qwen reasoning dikontrol via `chat_template_kwargs`
- `<think>...</think>` dibersihkan sebelum ditampilkan

## Thinking / Reasoning Behavior
Use:
```json
"chat_template_kwargs": {
  "enable_thinking": false,
  "preserve_thinking": false
}
```

Default thinking: OFF.

Thinking ON hanya untuk analisis kompleks.

UI juga punya fallback untuk menghapus `<think>...</think>`.

## Completed
Technical:
- L40S detected
- Qwen downloaded
- vLLM installed
- model loaded
- inference works
- Indonesian/English tested
- reasoning tested
- OpenAI-compatible endpoint works
- CAI Application works
- FastAPI proxy works
- public endpoint works
- unauth access configured
- Gradio works
- Gradio → Qwen works

UX:
- Tempo Scan branding direction
- Dashboard mockup
- Ask AI mockup
- Settings mockup
- AI Monitoring mockup
- horizontal Gradio chat

## Not Yet Done
1. Real Tempo data integration
2. Trino/CDW connection (updated Milestone 5 direction)
3. Semantic layer
4. Text-to-SQL
5. SQL validator
6. Query execution
7. Result explanation
8. Chart generation
9. External data
10. Forecasting
11. AI monitoring implementation
12. Ground truth evaluation
13. Production target architecture
14. Production sizing/storage/security/HA

## Agentic Suitability
Qwen3.8-27B-AWQ cukup untuk PoC jika flow dikontrol.

Recommended:
User
→ Intent Router
→ Allowed Tool
→ SQL Generator
→ SQL Validator
→ Execute
→ Result Checker
→ Qwen Explain
→ Final Answer

Hindari unrestricted autonomous loop.

## Recommended Build Order
PHASE 1 — Foundation
1. Define data model
2. Build sample data
3. Connect Python → Trino/CDW
4. Build semantic layer

PHASE 2 — AI to Data
5. NL → SQL
6. SQL validation
7. Execute query
8. Return table
9. LLM explanation

PHASE 3 — Experience
10. Generate chart
11. Follow-up chat
12. Dashboard
13. Executive insight cards

PHASE 4 — Advanced Value
14. Forecasting
15. External data
16. Competitor/weather analysis
17. Recommendations

PHASE 5 — Validation
18. Ground truth
19. Latency
20. Accuracy
21. Monitoring
22. Final demo story

## Recommended PoC Scope
Hero: Executive Commercial Intelligence

Supporting: Natural Language → Sales Analysis

Added Value: Forecast + External Signal

Demo story:
1. Executive opens dashboard
2. sees sales drop in Jawa Barat
3. asks AI why
4. AI queries trusted data
5. AI returns drivers
6. optionally combines external signals
7. recommends actions
8. asks forecast next month
9. AI returns forecast + chart
10. close with CDP = trusted/governed data, Cloudera AI = model + AI experience

## Open Action Items
- request sample data/schema
- request business questions + ground truth
- check Ingram infra
- complete NDA
- define high-level production architecture
- define production storage architecture
- validate sizing from PoC result
