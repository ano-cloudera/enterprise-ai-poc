# Reusable Ask Data Frontend — Capability Brief (PoC / Demo)

**Repo path:** `frontend/`  
**Audience:** Product/design (e.g. PoC2, ChatGPT design prompts), engineering onboarding  
**Updated:** 8 Oct 2026  

This document describes what the current Next.js UI **can do today**, what it **expects from the backend**, and what is **explicitly out of scope** so you can extend it as a reusable Cloudera PoC shell without re-discovering the codebase.

---

## 1. Product positioning

| Aspect | Description |
|--------|-------------|
| **What it is** | Enterprise **Ask Data** chat: grounded analytics with structured answers (narrative + table + chart + metadata), not a generic token-streaming chatbot only. |
| **Reuse goal** | White-label demo/PoC for Cloudera customers; swap backend if API contract stays compatible. |
| **Not in this FE** | Full BI dashboard, monitoring console, browser `ui_actions` executor (removed or never wired in V2). |

---

## 2. Technology stack

| Layer | Choice |
|-------|--------|
| Framework | Next.js (App Router), React client components |
| Styling | Tailwind + Cloudera-oriented design tokens |
| State | Redux Toolkit — model selection only (`modelSelectionSlice`) |
| Charts | Recharts (bar, line, area, scatter, pie) |
| PDF | jsPDF + jspdf-autotable; chart capture from DOM |
| Icons | Lucide React |
| Tests | Vitest (stream, settings, PDF, sessions, clarification) |
| Deploy | Cloudera AI Application — `frontend/app_cai_frontend.py` |
| API access | Browser calls same-origin **`/api/*`**; Next.js rewrites proxy to `BACKEND_API_URL` (CORS workaround for CAI gateway) |

**Key files:** `src/views/AskDataPage.tsx`, `src/views/SettingsPage.tsx`, `src/layout/AppShell.tsx`, `src/lib/api.ts`, `src/types/api.ts`, `src/config/appConfig.ts`.

---

## 3. Navigation and shell

### 3.1 Routes

| Route | Page |
|-------|------|
| `/` | Ask Data (main chat) |
| `/settings` | AI model selection |

Dashboard and Monitoring were **removed** in Frontend V2 (see `frontend/README.md`).

### 3.2 App shell features

- **Sidebar (desktop):** collapse/expand, brand mark, primary nav, **New Chat**, **Recent** conversation list.
- **Header:** configurable title (`customerName` + `appName`), static **Database** status chip (visual only — not wired to `/health`), **Download PDF** when the thread has messages.
- **Mobile:** bottom navigation; session list hidden when sidebar collapsed.
- **Chat layout context:** Ask Data registers session sidebar state and header chrome (PDF, minimal header on empty state).

### 3.3 White-label configuration

Via `NEXT_PUBLIC_*` and `src/config/appConfig.ts`:

- App name, customer name (header prefix), tagline, sidebar product name
- Chat placeholder, empty-state title/description
- Logo paths (`public/`)
- Nav labels (Ask Data, Settings)

See `frontend/.env.example` for the full list.

---

## 4. Ask Data — conversation

### 4.1 Core chat

| Feature | Behavior |
|---------|----------|
| Multi-turn | Stable `session_id` (UUID) sent on each request; backend owns server-side history |
| Composer | Auto-growing textarea; Enter to send, Shift+Enter newline; **Stop** aborts in-flight stream |
| Model gate | Submit disabled until a model is loaded and selected |
| Starter prompts | Empty state loads **3** questions from `GET /random-queries?limit=3` |
| Scroll | Auto-scroll on new messages / loading |

### 4.2 Streaming protocol

- **Endpoint:** `POST /api/chat/stream` (proxied to backend `/chat/stream`)
- **Events:**
  - `progress` — `stage`, `label`, optional `detail` (OSSIE/LangGraph node labels)
  - `done` — full `ChatResponse` payload
- **Not supported:** streaming assistant text tokens; user sees progress until the full structured response arrives.
- **Timeout:** client abort via `NEXT_PUBLIC_CHAT_STREAM_TIMEOUT_MS` (default **180000** ms)
- **SSE parsing:** buffered drain in `src/lib/api.ts` (handles final chunk with `done=true`)

### 4.3 Progress UX

- In-flight: `StreamingProgress` — 5-step rail mapped from backend stages + technical trace list
- After complete: per-turn **process snapshot** stored in session; **View process** in `ResponseFooter` opens `ProgressStepsPanel` (summary + detail levels)

---

## 5. Ask Data — structured answer rendering

Backend contract: `ChatResponse` in `src/types/api.ts`.

### 5.1 Response fields used

| Field | UI use |
|-------|--------|
| `status` | SUCCESS, CLARIFICATION, NO_DATA, UNSUPPORTED, ERROR |
| `strategy` | governed, clarification, conversational, sql_fallback, etc. |
| `answer` | `direct_answer`, `executive_summary`, `insights`, `business_implications`, `caveats`, `data_reference` |
| `data` | `columns`, `rows`, `row_count`, `governed_metric`, `unit_format`, `execution_ms` |
| `chart_spec` | type, title, x, y, series |
| `timings` | footer duration (`total_ms`) |
| `provider`, `model` | footer (provider name; model id not shown to user) |

### 5.2 Presentation blocks

1. **Section header** — title from `answerPresentation()` (e.g. Direct answer, Welcome, clarification)
2. **Status chip** — clarification / no data / unsupported when relevant
3. **Governed evidence warning** — if `strategy=governed` and SUCCESS but no rows/query citation (`hasGovernedEvidence`)
4. **Narrative** — `AnswerProse` on `direct_answer`; optional `executive_summary` if distinct
5. **Clarification quick replies** — `clarificationChoices()` → buttons resubmit as user message (sell-in vs sell-out, DC vs store stock, etc.)
6. **Insights** — bulleted list with icon
7. **Business implications** — highlighted card list
8. **Evidence block**
   - **KPI** — `KpiCard` when `chart_spec.type === 'kpi'`
   - **Chart** — `AnswerChart` for bar | line | area | scatter | pie
   - **Table** — `DataTable` with business labels and ID locale formatting
   - **Single row** — `SingleRowEvidence` when one row and no chart (compact “key figure”)
9. **Chart-first layout** — chart above narrative sections when visual chart exists; toggle **Show/Hide table detail**
10. **Data note** — merged caveats + provenance parsed from `data_reference` (`DataNote`)
11. **Footer** — `Provider · Strategy · Duration` + **View process**

### 5.3 Status normalization

`governedEvidence.ts` adjusts display when narrative claims success but SQL evidence is missing, or ERROR with partial data — avoids alarming UX during demos.

---

## 6. Session management (client)

| Feature | Implementation |
|---------|----------------|
| Storage | `localStorage` key `tempo-scan-v2.ask-data.sessions` |
| Cap | Max **20** sessions |
| Title | Derived from first user message |
| Pin | Pin/unpin via session ⋯ menu; pinned sort first |
| Delete | Remove locally + `DELETE /api/chat/sessions/{id}` (best effort) |
| Restore | Load messages; restore per-session model selection if saved |
| New chat | New UUID, clear thread |

**Not included:** cloud sync, accounts, share links, JSON export (PDF only).

---

## 7. Settings

| Feature | Behavior |
|---------|----------|
| Load models | `GET /models` → list with `available`, `reason` |
| Providers | qwen, gemini, openai (typed) |
| Selection UX | Dropdown; optional optgroup by provider; **Save model** (draft vs committed) |
| Persistence | Redux + `localStorage` `tempo-scan-v2.model-selection` |
| Default pick | Saved → Gemini → first available |

**Not included:** API keys, temperature, prompts, admin flags in UI.

---

## 8. PDF export

| Feature | Behavior |
|---------|----------|
| Trigger | Header **PDF** on Ask Data |
| Content | App title, turns, user/assistant text, tables (row cap), chart snapshots from conversation DOM |
| Filename | `tempo-scan-{title}-{date}.pdf` |
| Export mode | Temporarily expands hidden tables for capture |

---

## 9. Backend API surface (frontend expectations)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/models` | Model discovery |
| GET | `/random-queries?limit=N` | Starter questions |
| POST | `/chat/stream` | Ask Data SSE |
| DELETE | `/chat/sessions/{sessionId}` | Optional session cleanup |

Proxy: `frontend/next.config.mjs` → `BACKEND_API_URL` (default `http://127.0.0.1:8000`).

---

## 10. Explicit gaps (foundation v2 vs this UI)

These exist in broader project docs or older milestones but **are not in Frontend V2**:

- Dashboard + shared filter/chart state
- **`ui_actions`** whitelist execution (SET_FILTER, RENDER_CHART, …)
- Monitoring / real health badge
- Thumbs up/down feedback
- Assistant token streaming
- `NEXT_PUBLIC_AGENT_CHIP` (defined in `.env.example`, **not rendered** in UI)
- Authentication, RBAC, multi-tenant
- Full i18n (mostly English UI copy; ID number/date formatting in places)

---

## 11. Engineering notes for reuse

- **Contract-first:** keep `src/types/api.ts` aligned with FastAPI `AskDataResponse`.
- **Same-origin API:** preserve `/api` proxy pattern for CAI deployments.
- **Demo latency:** ~40–60 s per governed turn is normal; UI waits for `done` — design for **perceived speed** separately (partial results, skeletons) if PoC2 requires “ChatGPT-like” feel.
- **Tests:** run `cd frontend && npm test` before rebranding refactors.

---

## 12. ChatGPT / design prompt (copy-paste)

```text
We have a Next.js reusable Ask Data FE for Cloudera PoCs: SSE progress (not token stream),
structured answers (direct answer, insights, implications, caveats, Recharts, tables, KPI,
clarification chips, governed-evidence warning, View process/trace, PDF export, local
session history with pin, Settings with backend-driven models, white-label via env,
/api proxy to FastAPI. No dashboard, ui_actions, auth, or monitoring.

Design PoC2 extensions:
1) Information architecture for multi-project or multi-domain demos
2) UX that improves perceived speed without backend changes first
3) Enterprise trust features (lineage, export, operator/admin)
4) Theming / multi-customer branding
5) What NOT to add to keep a thin reusable shell
```

---

## 13. Extension ideas (not implemented — brainstorming only)

- Partial SSE: show table/chart after query, narrative later
- Collapsible data note; suggested follow-up chips from backend
- Configurable golden-question packs per industry (YAML/JSON)
- Live health/engine badge from `GET /health`
- Optional dashboard lane reintroduced with strict `ui_actions` whitelist
- Share read-only transcript link; CSV per turn
- Dark mode + per-customer theme tokens
- Demo recording mode (on-screen step labels, timer)

---

## Related docs

- `frontend/README.md` — local run, CAI deploy, troubleshooting
- `README.md` — backend architecture v2 (LangGraph, structured response)
- `skills/frontend_skill.md` — alternate buildless React pattern (not this Next.js app)
