from __future__ import annotations

from app.services import markdown_chart_adapter

# Captured verbatim from a real Agent Studio run against
# Tempo-Scan-Intelligence-Prod (Master Agent = Qwen, after the delegation
# few-shot fix) for the question "Berapa total Gross Sales TEMPO selama Q4
# 2024?" - see the "Agent Studio Master Delegation Bug" investigation.
GROSS_SALES_Q4_MARKDOWN = """### Penjelasan Total Gross Sales TEMPO Q4 2024

Berdasarkan data terkelola (governed) dari sistem TEMPO, berikut adalah penjelasan mengenai hasil kuartal keempat tahun 2024:

#### Definisi Metrik
Metrik yang digunakan adalah **Gross Billing Value** (Total Gross Sales). Metrik ini merepresentasikan total nilai tagihan bruto yang diakui secara resmi dalam sistem untuk periode tertentu, sebelum pengurangan diskon, retur, atau penyesuaian lainnya.

#### Hasil Data

| Bulan | Gross Sales (IDR) |
|---|---|
| Oktober 2024 | 1.371.960.298.317 |
| November 2024 | 1.195.251.225.676 |
| Desember 2024 | 1.274.654.263.080 |

Total Gross Sales TEMPO untuk periode **Q4 2024 (Oktober - Desember)** tercatat sebesar:

> **Rp 3.841.865.787.073**

Angka ini merupakan akumulasi dari seluruh penjualan yang diakui secara resmi selama kuartal tersebut.

#### Implikasi Bisnis
Angka ini memberikan gambaran tentang skala pendapatan bruto perusahaan pada akhir tahun 2024. Sebagai metrik "Gross", angka ini mencerminkan potensi pendapatan maksimal sebelum penyesuaian komersial. Untuk analisis profitabilitas yang lebih akurat, angka ini sebaiknya dibandingkan dengan metrik "Net Sales" atau "Revenue" yang telah memperhitungkan diskon dan retur.

#### Status & Referensi Data
- **Status Governance:** Data ini berasal dari metric yang **terkelola (governed)** dan telah tervalidasi secara teknis.
- **Catatan Penting:** Metrik ini masih dalam tahap **menunggu konfirmasi bisnis final**. Oleh karena itu, angka ini sebaiknya digunakan sebagai referensi awal hingga validasi bisnis selesai dilakukan.
- **Metric ID:** `SI-01`
- **Source View:** `gold.rpt_sap_monthly_executive_semantic`
"""


def test_extracts_summary_from_first_paragraph() -> None:
    parsed = markdown_chart_adapter.parse(GROSS_SALES_Q4_MARKDOWN, "Berapa total Gross Sales TEMPO selama Q4 2024?")
    assert "governed" in parsed.answer.summary.lower() or "terkelola" in parsed.answer.summary.lower()


def test_extracts_table_rows_with_normalized_numbers() -> None:
    parsed = markdown_chart_adapter.parse(GROSS_SALES_Q4_MARKDOWN, "Berapa total Gross Sales TEMPO selama Q4 2024?")
    assert parsed.data.columns == ["Bulan", "Gross Sales (IDR)"]
    assert parsed.data.rows == [
        {"Bulan": "Oktober 2024", "Gross Sales (IDR)": 1371960298317},
        {"Bulan": "November 2024", "Gross Sales (IDR)": 1195251225676},
        {"Bulan": "Desember 2024", "Gross Sales (IDR)": 1274654263080},
    ]


def test_guesses_currency_unit_format() -> None:
    parsed = markdown_chart_adapter.parse(GROSS_SALES_Q4_MARKDOWN, "Berapa total Gross Sales TEMPO selama Q4 2024?")
    assert parsed.data.unit_format == "currency_idr"
    assert parsed.chart_spec is not None
    assert parsed.chart_spec.unit_format == "currency_idr"


def test_chart_type_defaults_to_bar_without_trend_keywords() -> None:
    parsed = markdown_chart_adapter.parse(GROSS_SALES_Q4_MARKDOWN, "Berapa total Gross Sales TEMPO selama Q4 2024?")
    assert parsed.chart_spec is not None
    assert parsed.chart_spec.type == "bar"


def test_chart_type_is_line_when_question_mentions_trend() -> None:
    parsed = markdown_chart_adapter.parse(GROSS_SALES_Q4_MARKDOWN, "Bagaimana tren Gross Sales per bulan selama Q4 2024?")
    assert parsed.chart_spec is not None
    assert parsed.chart_spec.type == "line"


def test_chart_type_is_pie_when_question_mentions_share() -> None:
    parsed = markdown_chart_adapter.parse(GROSS_SALES_Q4_MARKDOWN, "Berapa persentase kontribusi tiap bulan terhadap Gross Sales Q4 2024?")
    assert parsed.chart_spec is not None
    assert parsed.chart_spec.type == "pie"


def test_chart_series_carries_raw_numeric_values() -> None:
    parsed = markdown_chart_adapter.parse(GROSS_SALES_Q4_MARKDOWN, "Berapa total Gross Sales TEMPO selama Q4 2024?")
    assert parsed.chart_spec is not None
    assert parsed.chart_spec.x == ["Oktober 2024", "November 2024", "Desember 2024"]
    assert len(parsed.chart_spec.series) == 1
    assert parsed.chart_spec.series[0].name == "Gross Sales (IDR)"
    assert parsed.chart_spec.series[0].data == [1371960298317, 1195251225676, 1274654263080]


def test_no_table_returns_empty_data_and_no_chart() -> None:
    parsed = markdown_chart_adapter.parse("Halo! Saya SCAN, asisten TEMPO Anda.", "Halo")
    assert parsed.data.columns == []
    assert parsed.data.rows == []
    assert parsed.chart_spec is None


def test_single_column_table_produces_no_chart() -> None:
    markdown = """### Domain yang didukung

| Domain |
|---|
| Sales / Sell-In |
| B2B / Sell-Out |
"""
    parsed = markdown_chart_adapter.parse(markdown, "Domain apa saja yang didukung?")
    assert parsed.data.columns == ["Domain"]
    assert len(parsed.data.rows) == 2
    assert parsed.chart_spec is None


def test_implikasi_bisnis_section_becomes_a_driver() -> None:
    parsed = markdown_chart_adapter.parse(GROSS_SALES_Q4_MARKDOWN, "Berapa total Gross Sales TEMPO selama Q4 2024?")
    assert any("skala pendapatan bruto" in driver for driver in parsed.answer.drivers)


def test_mixed_governance_and_reference_section_keeps_only_the_business_caveat() -> None:
    # "Status & Referensi Data" mixes a genuine governance caveat bullet
    # with technical Metric ID/Source View bullets under one heading, as
    # seen in real Analysis Agent output - only the caveat bullets should
    # survive, never the raw metric_id/source_view identifiers.
    parsed = markdown_chart_adapter.parse(GROSS_SALES_Q4_MARKDOWN, "Berapa total Gross Sales TEMPO selama Q4 2024?")
    assert any("menunggu konfirmasi bisnis final" in caveat for caveat in parsed.answer.caveats)
    assert not any("SI-01" in caveat or "rpt_sap_monthly" in caveat for caveat in parsed.answer.caveats)


def test_falls_back_to_later_paragraphs_when_no_heading_keyword_matches() -> None:
    # None of these headings contain any _DRIVER_HEADING_KEYWORDS /
    # _CAVEAT_HEADING_KEYWORDS substring, exercising the fully-unfamiliar-
    # heading-style fallback path.
    markdown = """### Hasil Utama

Total Gross Sales TEMPO Q4 2024 adalah Rp 3.8T.

#### Faktor Pendorong

Angka ini naik dibandingkan kuartal sebelumnya, didorong oleh kenaikan Sell-In di bulan Desember.

#### Perlu Diketahui

Data ini masih bersifat sementara sampai proses rekonsiliasi akhir bulan selesai.
"""
    parsed = markdown_chart_adapter.parse(markdown, "Berapa Gross Sales Q4 2024?")
    assert parsed.answer.summary == "Total Gross Sales TEMPO Q4 2024 adalah Rp 3.8T."
    assert any("Sell-In di bulan Desember" in driver for driver in parsed.answer.drivers)
    assert any("rekonsiliasi akhir bulan" in driver for driver in parsed.answer.drivers)
