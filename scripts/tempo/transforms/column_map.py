from __future__ import annotations

import re

import pandas as pd

# Explicit renames for Dec 16-31 Sales export and other known aliases
EXPLICIT_RENAMES: dict[str, str] = {
    "DO Amount": "do_amt",
    "Net Sales": "net_sales",
    "Lead = 4": "lead_time",
    "Route List": "route_list",
    "KA Group": "ka_group",
    "Kode PLU": "kode_plu",
    "Cust Id": "customer_id",
    "Cust Code": "customer_code",
    "cust_id": "customer_id",
    "cust_code": "customer_code",
    "Material_code": "material_id",
    "Material": "material_id",
    "PLU": "plu",
    "TGL_DCP": "survey_date",
    "Stok_akhir": "stok_akhir",
    "Program_Status": "program_status",
}

# Common SAP InfoObject / key figure names
SAP_RENAMES: dict[str, str] = {
    "0MATERIAL": "material_id",
    "0CUSTOMER": "customer_id",
    "0SALESORG": "sales_org",
    "0SALES_OFF": "sales_office",
    "0SALES_GRP": "sales_group",
    "0SOLD_TO": "sold_to",
    "0CALMONTH": "calmonth",
    "0CALMONTH2": "calmonth2",
    "0CALDAY": "calday",
    "0CALYEAR": "calyear",
    "0FISCPER": "fiscper",
    "0BILL_TYPE": "bill_type",
    "0DOC_TYPE": "doc_type",
    "0CUST_GRP3": "cust_group",
    "0BASE_UOM": "base_uom",
    "0BILL_QTY": "bill_qty",
    "0PRODUCT": "product",
    "0STOR_LOC": "stor_loc",
    "0STOCKCAT": "stock_cat",
    "0STOCKTYPE": "stock_type",
    "0VENDOR": "vendor",
    "0UPD_DATE": "upd_date",
    "0RECORDTP": "record_tp",
    "0AF_CGR6": "af_cgr6",
    "Plant": "plant",
    "Vendor": "vendor",
    "BILL_VAL": "bill_val",
    "CN_AMT": "cn_amt",
    "CN_QTY": "cn_qty",
    "DO_AMT": "do_amt",
    "DO_QTY": "do_qty",
    "PO_AMT": "po_amt",
    "PO_QTY": "po_qty",
    "NSP": "nsp",
    "ZCOST": "zcost",
    "ZSUBHUB": "subhub",
    "ZDIS_D8": "zdis_d8",
    "ZIOCH0042": "zioch0042",
    "Currency": "currency",
    "BRANCH": "branch",
}


def _to_snake_case(name: str) -> str:
    cleaned = name.strip()
    if cleaned in EXPLICIT_RENAMES:
        return EXPLICIT_RENAMES[cleaned]
    if cleaned in SAP_RENAMES:
        return SAP_RENAMES[cleaned]
    if cleaned.startswith("0") and cleaned[1:].replace("_", "").isalnum():
        return cleaned[1:].lower()
    if cleaned.startswith("DIS_") or cleaned.startswith("DISC"):
        return cleaned.lower()
    if re.fullmatch(r"ZIOKF\d{4}", cleaned):
        return cleaned.lower()
    normalized = re.sub(r"[^\w\s]", " ", cleaned)
    normalized = re.sub(r"\s+", "_", normalized.strip().lower())
    return normalized or "unnamed_column"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {_col: _to_snake_case(str(_col)) for _col in df.columns}
    out = df.rename(columns=renamed)
    # Avoid duplicate column names after normalization
    deduped: dict[str, str] = {}
    seen: dict[str, int] = {}
    for original, new_name in renamed.items():
        count = seen.get(new_name, 0)
        seen[new_name] = count + 1
        deduped[original] = new_name if count == 0 else f"{new_name}_{count}"
    return df.rename(columns=deduped)
