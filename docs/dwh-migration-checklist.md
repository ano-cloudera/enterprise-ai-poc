# DWH Migration Checklist — Impala/Iceberg Cluster Cutover

Context: full cluster migration (compute + storage both moving), both old and
new Impala clusters reachable over VPN, tables are Iceberg (S3/HDFS/ADLS).
Goal: minimum-effort, verifiable migration of everything this project's
governed semantic layer depends on.

## Why this is smaller than it looks

Every Gold-layer object this project uses is a `CREATE VIEW`, not a
`CREATE TABLE` — confirmed by grepping all 44 `CREATE VIEW`/`CREATE TABLE`
statements across `datasets/audit/*.sql` and `datasets/gold/*.sql` (44 views,
0 tables). That means **only the 9 silver tables below need real data
transfer** — every Gold view is re-created by re-running SQL already written
and version-controlled in this repo, not by copying data.

## Step 1 — Migrate the 9 silver tables (the only real data transfer)

```text
silver.b2b_oct_dec_2024
silver.picking_okt_des_24
silver.sales_oct_dec_2024
silver.sat_oos_okt_des_2024
silver.sat_promo_des_24
silver.service_level_oct_dec_2024
silver.stock_sat_idm_monthly_okt_des_24
silver.stock_tempo_oct_dec_2024
silver.unloading_okt_des_24
```

Since both clusters are Iceberg and VPN-connected, from Impala on the NEW
cluster:

```sql
-- Repeat for each of the 9 tables above.
CREATE TABLE silver.sales_oct_dec_2024
LIKE ICEBERG <old_cluster_catalog>.silver.sales_oct_dec_2024;

INSERT INTO silver.sales_oct_dec_2024
SELECT * FROM <old_cluster_catalog>.silver.sales_oct_dec_2024;
```

The exact `<old_cluster_catalog>` syntax depends on how the two clusters are
federated (a shared Hive Metastore/Glue Catalog reachable from both, a
cross-cluster query engine, or an Impala `CREATE TABLE ... TBLPROPERTIES`
pointing at the old cluster's catalog URI) — confirm the working syntax with
whoever manages the catalog before running this at scale; try it on the
smallest table first (`silver.sat_promo_des_24`, single-month scope) as a
dry run.

If direct cross-cluster `INSERT ... SELECT` isn't available, fall back to
Iceberg's own snapshot/manifest export-import tooling (e.g. a Spark job using
`RewriteTablePath`) instead of a naive Parquet export/reimport — it preserves
Iceberg's snapshot history and is typically faster than row-by-row copy for
large tables.

**Row-count sanity check** after each table copies — compare
`SELECT COUNT(*) FROM silver.<table>` on old vs new cluster. A mismatch means
stop and investigate before moving to Step 2; don't rebuild Gold views on top
of a silver table you haven't confirmed matches.

## Step 2 — Re-run every Gold view's CREATE VIEW, in this order

Sources, in the order they were built (later ones sometimes reference earlier
ones — check each file's own header comment for exact dependencies before
assuming order doesn't matter):

1. `datasets/audit/gold_audit.sql` — the original 5 baseline semantic views
   plus their `corr_*` building-block views (contains the actual
   `CREATE VIEW` statements inline, not just investigation queries — read it
   before running, some of its blocks are `SELECT`-only audits, not DDL).
2. Nine-domain journey views — DDL referenced from
   `datasets/audit/20_gold_journey_fase_a_draft.sql` and
   `datasets/audit/21_gold_journey_fase_b_draft.sql`.
3. `datasets/gold/23_rpt_sat_promo_material_december_semantic.sql` — SAT
   Promo.
4. `datasets/gold/24_rpt_sap_customer_office_material_month_semantic.sql` —
   Sales/Sell-In customer + sales_office breakdown. Contains **two**
   `CREATE VIEW` statements. Whether these two specifically were run as one
   block or separately in the original Workbench was never confirmed either
   way — given the B2B `ParseException` below happened with the same shape
   (two `CREATE VIEW`s + a comment between them, highlighted together),
   **run each `CREATE VIEW` in this file separately** to be safe, don't
   assume it's fine just because it wasn't the one that failed.
5. `datasets/gold/25a_rpt_b2b_customer_branch_estore_semantic.sql` and
   `datasets/gold/25b_rpt_b2b_customer_material_plu_semantic.sql` — B2B
   customer breakdown, already split into two single-statement files
   because the combined version threw a `ParseException` in the original
   Workbench (see each file's header comment) — run each as-is.
6. `datasets/gold/26_rpt_service_level_sales_office_semantic.sql` — Service
   Level sales_office breakdown (single statement, no split needed).

After each `CREATE VIEW`, run that same file's paired verification queries
from `datasets/audit/` (duplicate-grain check expecting `0`, reconciliation
against the already-migrated silver totals) before moving to the next file —
same discipline already used when these views were first built and
Workbench-verified in this project.

## Step 3 — Re-point application config, not code

Nothing in `tempo_core.ossie.yaml` or `backend/app/ossie/*.py` needs to
change — they reference `gold.<view_name>`, not a physical host. Only
connection settings change, all in `docs/cai-application-deployment-config.md`
(placeholders there, fill in for the new cluster):

- `IMPALA_HOST` — the new cluster's coordinator hostname. **This is the one
  value that must never be copied from the old environment** — it's cluster-
  specific by definition.
- Re-verify `IMPALA_PORT`/`IMPALA_AUTH_MECHANISM`/`IMPALA_USE_SSL`/
  `IMPALA_USE_HTTP_TRANSPORT`/`IMPALA_HTTP_PATH` still match the new
  cluster's actual setup — don't assume they're identical just because the
  old ones worked.
- Each Agent Studio custom tool under
  `projects/tempo_scan_impala/agent_studio_tools/*/` also takes Impala
  credentials as its own User Parameters (Agent Studio's tool Configure UI
  has no separate env-var surface) — these need the same `IMPALA_HOST`
  update, tool by tool, when the Agent Studio workflow is rebuilt on the new
  environment.

## Step 4 — Contract validation against the new cluster

```bash
PYTHONPATH=backend python3 scripts/validate_tempo_impala_contract.py --json
```

Expect `valid: true`, `datasets: 20`, `metrics: 61`, `golden_questions: 81`
(this only validates the YAML/Python contract shape, not live Impala
connectivity — it doesn't need `IMPALA_HOST` set to pass). For a live check
against the new cluster's actual data, re-run the reconciliation queries from
Step 2 one more time end-to-end, and spot-check a handful of golden questions
through `resolve_semantic_object`'s CLI tool against the new
`IMPALA_HOST`.

## What does NOT need migrating

- `tempo_core.ossie.yaml`, `tempo_governance.yaml`, `golden_questions.yaml` —
  pure config, schema/view names only, no embedded connection info.
- `backend/app/ossie/*.py` — the resolver/registry code.
- Agent Studio Backstories/tool Python source
  (`projects/tempo_scan_impala/agent_studio_tools/*/tool.py`) — only their
  `UserParameters` values (Impala credentials) need updating, not the code.
