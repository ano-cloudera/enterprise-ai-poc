"""Deterministic conversational answers when the LLM provider fails."""

from __future__ import annotations

from app.core.models import AnalysisOutput


def deterministic_sell_in_vs_sell_out_answer() -> dict:
    text = (
        "Sell-In Tempo adalah penjualan/pengiriman dari Tempo ke jaringan trade "
        "(sales office, gross billing ke customer) — sudut pandang shipment Tempo. "
        "Sell-Out Alfamart adalah penjualan partner melalui jaringan DC/outlet Alfamart "
        "(metrik B2B sell-out) — pergerakan di sisi partner. Angka keduanya tidak "
        "boleh disamakan; selisihnya mengindikasikan pipeline vs pergerakan retail."
    )
    return AnalysisOutput(
        direct_answer=text,
        executive_summary=text,
        insights=[
            "Contoh sell-in: total gross billing Tempo Q4 2024 per sales office.",
            "Contoh sell-out: top DC Alfamart by nilai sell-out partner Q4 2024.",
        ],
        business_implications=[],
        caveats=["Definisi domain; tidak ada query governed di turn ini."],
        data_reference="TEMPO domain definitions (no query executed).",
        chart_spec=None,
    ).model_dump()


def deterministic_promo_uplift_proxy_explain() -> dict:
    text = (
        "Proxy uplift promo SAT membandingkan General Trade Sell-In billing material yang sama: "
        "baseline November 2024 vs Desember 2024 (bulan observasi promo). Uplift revenue/volume "
        "bukan dampak promo Alfamart langsung di sell-out partner; ini indikator lintas-channel "
        "untuk material yang sama di SAP."
    )
    return AnalysisOutput(
        direct_answer=text,
        executive_summary=text,
        insights=[
            "Material rank 1 uplift mengacu pada baris teratas dari ranking Desember 2024.",
            "Untuk angka governed, lihat kolom revenue_uplift / volume_uplift pada dataset proxy.",
        ],
        business_implications=[],
        caveats=["Proxy GT sell-in; bukan ROI promo outlet Alfamart."],
        data_reference="sat_promo_material_uplift methodology (no new query required).",
        chart_spec=None,
    ).model_dump()


def deterministic_capability_overview_answer() -> dict:
    text = (
        "Untuk review manajemen Q4 2024 (Oktober–Desember), Anda dapat menanyakan: "
        "Sell-In Tempo (sales office, material, gross billing), Sell-Out partner Alfamart "
        "(cabang/DC, produk), stok gudang Tempo dan stok SAT (DC/store), OOS SAT, "
        "service level/fill rate, durasi picking & unloading, serta observasi promo SAT."
    )
    return AnalysisOutput(
        direct_answer=text,
        executive_summary=text,
        insights=[
            "Gunakan follow-up untuk drill-down (mis. rank 1 → detail material/DC).",
            "Sistem akan klarifikasi jika grain sell-in vs sell-out ambigu.",
        ],
        business_implications=[],
        caveats=["Cakupan PoC: partner Alfamart, periode Q4 2024."],
        data_reference="TEMPO governed capability catalog (no query executed).",
        chart_spec=None,
    ).model_dump()
