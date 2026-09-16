from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import csv
import calendar
import math
import random
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "projects" / "tempo_scan" / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)
random.seed(42)

regions = {
    "Jawa Barat": ["Bandung", "Bekasi"],
    "Jawa Timur": ["Surabaya"],
    "Jawa Tengah": ["Semarang"],
    "Sumatera": ["Medan"],
    "Kalimantan": ["Balikpapan"],
    "Sulawesi": ["Makassar"],
}
products = [
    ("P001", "Tempra", "Fever & Pain", 1.05),
    ("P002", "Bodrex Flu & Batuk", "Cough & Cold", 1.20),
    ("P003", "Hemaviton C1000", "Vitamin", 0.92),
    ("P004", "Vidoran Smart", "Multivitamin", 0.78),
    ("P005", "Marina Skin Care", "Skin Care", 0.70),
]
channels = [
    ("C01", "General Trade", 1.15),
    ("C02", "Modern Trade", 1.00),
    ("C03", "E-commerce", 0.68),
    ("C04", "Hospitals & Institutions", 0.46),
]
region_factor = {
    "Jawa Timur": 1.18,
    "Jawa Barat": 1.00,
    "Jawa Tengah": 0.86,
    "Sumatera": 0.72,
    "Kalimantan": 0.55,
    "Sulawesi": 0.46,
}

start = date(2024, 1, 1)
end = date(2024, 3, 31)
rows = []
inv_rows = []
outlet_seq = 1
outlets = {}
for region, cities in regions.items():
    for city in cities:
        outlets[city] = [
            (f"O{outlet_seq:03d}", f"{city} Prime Pharmacy", "Pharmacy"),
            (f"O{outlet_seq+1:03d}", f"{city} Health Mart", "Retail"),
        ]
        outlet_seq += 2

current = start
while current <= end:
    month_factor = {1: 0.88, 2: 0.98, 3: 1.08}[current.month]
    seasonal = 1 + 0.05 * math.sin(current.timetuple().tm_yday / 5)
    for region, cities in regions.items():
        for city in cities:
            for outlet_id, outlet_name, outlet_type in outlets[city]:
                for product_id, product_name, category, product_factor in products:
                    stockout = 0
                    if (
                        current.month == 3
                        and region == "Jawa Barat"
                        and category == "Cough & Cold"
                        and city in {"Bandung", "Bekasi"}
                        and 8 <= current.day <= 21
                        and outlet_name.endswith("Prime Pharmacy")
                    ):
                        stockout = 1
                    closing_stock = 0 if stockout else max(5, int(random.gauss(95, 24)))
                    inv_rows.append({
                        "inventory_date": current.isoformat(),
                        "product_id": product_id,
                        "product_name": product_name,
                        "product_category": category,
                        "outlet_id": outlet_id,
                        "outlet_name": outlet_name,
                        "region_name": region,
                        "city": city,
                        "opening_stock": closing_stock + random.randint(10, 45),
                        "closing_stock": closing_stock,
                        "available_stock": closing_stock,
                        "stockout_flag": stockout,
                        "days_of_supply": 0 if stockout else round(closing_stock / random.uniform(8, 15), 1),
                    })
                    for channel_id, channel_name, channel_factor in channels:
                        base = 52.0 * region_factor[region] * product_factor * channel_factor * month_factor * seasonal
                        noise = random.uniform(0.90, 1.10)
                        multiplier = 1.0
                        if current.month == 3 and region == "Jawa Barat":
                            multiplier *= 0.90
                            if category == "Cough & Cold":
                                multiplier *= 0.72
                            if channel_name == "General Trade":
                                multiplier *= 0.85
                            if city == "Bandung":
                                multiplier *= 0.93
                            if city == "Bekasi":
                                multiplier *= 0.90
                            if stockout:
                                multiplier *= 0.55
                        amount = round(base * noise * multiplier, 3)
                        qty = max(1, int(amount * random.uniform(3.8, 5.4)))
                        rows.append({
                            "sales_date": current.isoformat(),
                            "region_name": region,
                            "province": region,
                            "city": city,
                            "product_id": product_id,
                            "product_name": product_name,
                            "product_category": category,
                            "brand": "Tempo Scan",
                            "outlet_id": outlet_id,
                            "outlet_name": outlet_name,
                            "outlet_type": outlet_type,
                            "channel_id": channel_id,
                            "channel_name": channel_name,
                            "customer_segment": "Consumer Health",
                            "sales_amount": amount,
                            "sales_qty": qty,
                            "transaction_count": max(1, int(qty / random.uniform(2.5, 4.0))),
                            "avg_selling_price": round(amount * 1_000_000 / qty, 2),
                        })
    current += timedelta(days=1)

for filename, data in (("commercial_sales_daily.csv", rows), ("commercial_inventory_daily.csv", inv_rows)):
    path = OUT / filename
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)
    print(f"wrote {len(data):,} rows -> {path}")

# Compact forecast-only history: monthly region/product/channel grain. A separate
# RNG keeps the established Jan-Mar 2024 daily hero fixture byte-stable.
history_rng = random.Random(20260915)
history_rows = []
history_month = date(2022, 4, 1)
history_end = date(2023, 12, 1)
month_index = 0
while history_month <= history_end:
    days = calendar.monthrange(history_month.year, history_month.month)[1]
    seasonality = 1 + 0.08 * math.sin((history_month.month - 1) * math.pi / 6)
    trend = 0.82 + month_index * 0.008
    for region, cities in regions.items():
        for _, product_name, _, product_factor in products:
            for _, channel_name, channel_factor in channels:
                amount = (
                    52.0
                    * len(cities)
                    * 2
                    * days
                    * region_factor[region]
                    * product_factor
                    * channel_factor
                    * seasonality
                    * trend
                    * history_rng.uniform(0.97, 1.03)
                )
                history_rows.append({
                    "sales_month": history_month.isoformat(),
                    "region_name": region,
                    "product_name": product_name,
                    "channel_name": channel_name,
                    "sales_amount": round(amount, 3),
                })
    month_index += 1
    history_month = date(history_month.year + (history_month.month == 12), history_month.month % 12 + 1, 1)

history_path = OUT / "commercial_sales_monthly_history.csv"
with history_path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(history_rows[0].keys()))
    writer.writeheader()
    writer.writerows(history_rows)
print(f"wrote {len(history_rows):,} rows -> {history_path}")

# The reusable product master is governed independently from transactional
# scenarios so portfolio alignment cannot alter historical or forecast values.
with (ROOT / "projects" / "tempo_scan" / "config.yaml").open(encoding="utf-8") as handle:
    governed_products = (yaml.safe_load(handle) or {}).get("product_master", [])
product_master_path = OUT / "commercial_product_master.csv"
with product_master_path.open("w", newline="", encoding="utf-8") as handle:
    fields = ["product_id", "product_name", "product_category", "product_categories", "synthetic"]
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    for product in governed_products:
        categories = product["product_categories"]
        writer.writerow({
            "product_id": product["product_id"], "product_name": product["product_name"],
            "product_category": "Nutritional" if "Nutritional" in categories else categories[0],
            "product_categories": "; ".join(categories), "synthetic": "true",
        })
print(f"wrote {len(governed_products):,} rows -> {product_master_path}")
