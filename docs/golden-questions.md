# Golden questions (governed OSSIE)

The **executable** suite for Impala/OSSIE is:

```text
backend/projects/tempo_scan_impala/ossie/golden_questions.yaml
```

Each entry defines question text, expected status (`supported`, `supported_with_caveat`, `needs_clarification`, `unsupported`, …), target metric/dataset where applicable, and business notes.

**Validation:**

```bash
.venv/bin/python scripts/validate_tempo_impala_contract.py
```

**Automated multi-turn UAT** (management judge + mechanical checks) lives under `backend/eval/` — see [`README.md`](README.md).

## Legacy synthetic suite

`projects/tempo_scan/semantic/golden_questions.yaml` covers the original DuckDB/synthetic resolver patterns (regions, channels, Jawa Barat scenarios). Tests may still reference it for foundation milestones; it is **not** the Q4 Impala contract.
