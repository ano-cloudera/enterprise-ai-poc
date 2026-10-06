"""Phase C2: DC Top-N stock compiles with dcname grain."""

from __future__ import annotations

from app.core.config import Settings
from app.semantic.context import SemanticContextService


def test_dc_penumpukan_compiles_group_by_dcname() -> None:
    settings = Settings(_env_file=None)
    ctx = SemanticContextService(settings.project_root / settings.ossie_project_id)
    q = (
        "Tampilkan 10 DC dengan penumpukan stok produk yang tertinggi, "
        "lalu analisa apakah ada yang bisa kita lakukan untuk memperbaiki situasi tersebut"
    )
    resolution = ctx.resolve(q)
    assert resolution.get("status") == "resolved"
    assert resolution.get("metric") == "sat_dc_stock_quantity"
    sql = ctx.compile_governed("sat_dc_stock_quantity", q, ["dcname"])
    assert "dcname" in sql.lower()
    assert "group by" in sql.lower()
    assert "order by" in sql.lower()
    assert "limit 10" in sql.lower()
