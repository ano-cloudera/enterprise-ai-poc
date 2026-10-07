# Ingram Impala — Gold view audit & CAI Kerberos

## 1. Log `GSSError` / `IMPALA_QUERY_FAILED` di CAI

That error is **Kerberos**, not a missing Gold view. The backend reached Impala auth and failed before SQL analysis.

**Checklist (Application `tempo-backend-v2`):**

1. Env Impala **Ingram**: `GSSAPI`, port `21050`, `IMPALA_USE_HTTP_TRANSPORT=false`, host coordinator (e.g. `cbase02.imid.local`).
2. `requirements-impala.txt` installed in `.venv-cai` including **`kerberos==1.3.1`** (needs `krb5` dev libs on image).
3. Valid **keytab or Kerberos identity** for the CAI runtime user (same as manual `kinit` on Workbench).
4. Redeploy/restart Application after env changes.

Smoke from Workbench (after `kinit`):

```bash
set -a && source .env && set +a   # IMPALA_CREDENTIAL_PROFILE=ingram
cd backend && PYTHONPATH=. python scripts/test_impala_ingram_env.py
```

---

## 2. Gold views — OSSIE contract (24 sources)

Authoritative list: `scripts/validate_tempo_impala_contract.py` → `EXPECTED_SOURCES` (must match `tempo_core.ossie.yaml` dataset `source` fields).

**Audit on Ingram:**

```bash
export IMPALA_CREDENTIAL_PROFILE=ingram
.venv/bin/python scripts/audit_gold_ingram.py
.venv/bin/python scripts/audit_gold_ingram.py --allow-empty   # warn only on empty tables
.venv/bin/python scripts/validate_ingram_gold_views.py --json  # if wired; prefer audit_gold_ingram
```

---

## 3. Views often deployed on AWS test first — sync to Ingram

| Gold view | Deploy helper / DDL |
|-----------|---------------------|
| `gold.corr_b2b_branch_material_month` | `backend/scripts/deploy_gold_enhancement_views.py` → `datasets/gold/01_*.sql` |
| `gold.rpt_sat_promo_b2b_sellout_uplift` | same → `02_*.sql` |
| `gold.corr_service_sales_office_cust_group_material_month` | same → `03_*.sql` (optional) |
| Sales office / customer material | `datasets/gold/24_*.sql`, `26_*.sql` |
| SAT promo December | `datasets/gold/23_*.sql` |
| Journey / baseline 5 + corr views | cluster migration bundle (`deploy_gold_views_lengkap.sql` on DWH — not always in git) |

After CREATE VIEW on Ingram:

```bash
.venv/bin/python scripts/validate_tempo_impala_contract.py
# restart backend CAI
```

Details: `docs/data-enhancement-views.md`.

---

## 4. AWS vs Ingram

| | AWS (tstenv06) | Ingram (Private Cloud) |
|--|----------------|-------------------------|
| Auth | LDAP + HTTP 443 | GSSAPI + TLS 21050 |
| Profile | `IMPALA_CREDENTIAL_PROFILE=aws` | `ingram` |
| Gold DDL | Deployed during PoC on test env | **Re-run same DDL** on Ingram `gold` — not copied by `git pull` |

Pull only updates **OSSIE YAML + backend code**; **Impala views are DBA/operator deploy** on each cluster.
