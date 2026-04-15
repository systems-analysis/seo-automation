"""
Сбор данных из Google Search Console.

Поддерживает пагинацию: API возвращает "top rows" по кликам,
rowLimit до 25 000 за запрос. Для больших выборок (>25 000 комбинаций
query/page/date) данные могут быть неполными — это ограничение API.

Использование:
    python scripts/fetch_search_data.py --days 7
    python scripts/fetch_search_data.py --days 30 --query "системный анализ"
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from common import get_credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
DATA_DIR = "data_search"
PAGE_SIZE = 25000
MAX_PAGES = 10


def fetch_search_analytics(site_url, days=7, query_filter=None, dimensions=None):
    """Fetch search analytics data with pagination.

    Returns:
        (all_rows, dimensions, is_partial): is_partial=True if pagination
        was interrupted by an error.
    """
    credentials = get_credentials(SCOPES)
    service = build("searchconsole", "v1", credentials=credentials)

    end_date = datetime.now(timezone.utc).date() - timedelta(days=3)
    # Search Console treats both dates as inclusive, so subtract days-1
    start_date = end_date - timedelta(days=days - 1)

    if dimensions is None:
        dimensions = ["query", "page", "date"]

    request_body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": dimensions,
        "rowLimit": PAGE_SIZE,
        "startRow": 0,
    }

    if query_filter:
        request_body["dimensionFilterGroups"] = [
            {
                "filters": [
                    {
                        "dimension": "query",
                        "operator": "contains",
                        "expression": query_filter,
                    }
                ]
            }
        ]

    print(f"📊 Запрос данных Search Console")
    print(f"   Сайт: {site_url}")
    print(f"   Период: {start_date} — {end_date} ({days} дн.)")
    if query_filter:
        print(f"   Фильтр: «{query_filter}»")
    print()

    all_rows = []
    page_num = 0
    is_partial = False

    while page_num < MAX_PAGES:
        page_num += 1
        try:
            response = (
                service.searchanalytics()
                .query(siteUrl=site_url, body=request_body)
                .execute()
            )
        except Exception as e:
            print(f"❌ Ошибка API (страница {page_num}): {e}")
            if all_rows:
                print(f"⚠️  Сохраняем {len(all_rows)} строк, собранных до ошибки")
                is_partial = True
                break
            sys.exit(1)

        rows = response.get("rows", [])
        all_rows.extend(rows)
        print(f"   📄 Страница {page_num}: {len(rows)} строк (всего: {len(all_rows)})")

        if len(rows) < PAGE_SIZE:
            break

        request_body["startRow"] += PAGE_SIZE
    else:
        # Loop ended because page_num hit MAX_PAGES ceiling,
        # NOT because last page was short — data may be truncated
        if all_rows:
            print(f"\n⚠️  Достигнут лимит страниц ({MAX_PAGES}), данные могут быть неполными")
            is_partial = True

    print(f"\n✅ Получено {len(all_rows)} строк данных")
    print()

    return all_rows, dimensions, is_partial


def save_to_csv(rows, dimensions, filename):
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, filename)
    headers = dimensions + ["clicks", "impressions", "ctr", "position"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            keys = row.get("keys", [])
            data = keys + [
                row.get("clicks", 0),
                row.get("impressions", 0),
                round(row.get("ctr", 0) * 100, 2),
                round(row.get("position", 0), 1),
            ]
            writer.writerow(data)

    print(f"💾 Сохранено: {filepath}")
    return filepath


def save_to_json(rows, dimensions, filename):
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, filename)

    processed = []
    for row in rows:
        keys = row.get("keys", [])
        entry = {}
        for i, dim in enumerate(dimensions):
            entry[dim] = keys[i] if i < len(keys) else ""
        entry["clicks"] = row.get("clicks", 0)
        entry["impressions"] = row.get("impressions", 0)
        entry["ctr"] = round(row.get("ctr", 0) * 100, 2)
        entry["position"] = round(row.get("position", 0), 1)
        processed.append(entry)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)

    print(f"💾 Сохранено: {filepath}")
    return filepath


def print_top_entries(rows, dimensions, limit=20):
    # Determine which dimension to group by and label accordingly
    group_dim = dimensions[0] if dimensions else "query"
    group_idx = 0
    if group_dim == "query":
        label = "Топ запросов по кликам"
        col_label = "Запрос"
    elif group_dim == "page":
        label = "Топ страниц по кликам"
        col_label = "Страница"
    else:
        label = f"Топ по «{group_dim}» по кликам"
        col_label = group_dim.capitalize()

    agg = {}
    for row in rows:
        keys = row.get("keys", [])
        if not keys:
            continue
        key = keys[group_idx]
        if key not in agg:
            agg[key] = {"clicks": 0, "impressions": 0, "weighted_pos": 0.0}
        impressions = row.get("impressions", 0)
        agg[key]["clicks"] += row.get("clicks", 0)
        agg[key]["impressions"] += impressions
        agg[key]["weighted_pos"] += row.get("position", 0) * impressions

    sorted_entries = sorted(agg.items(), key=lambda x: x[1]["clicks"], reverse=True)

    print(f"\n{'='*80}")
    print(f" {label} (топ-{limit})")
    print(f"{'='*80}")
    print(f" {col_label:<40} {'Клики':>7} {'Показы':>9} {'Ср.поз.':>8}")
    print(f" {'-'*40} {'-'*7} {'-'*9} {'-'*8}")

    for key, data in sorted_entries[:limit]:
        avg_pos = data["weighted_pos"] / data["impressions"] if data["impressions"] else 0
        display = key[:38] + ".." if len(key) > 40 else key
        print(f" {display:<40} {data['clicks']:>7} {data['impressions']:>9} {avg_pos:>8.1f}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Сбор данных из Google Search Console")
    parser.add_argument("--site", default="https://systems-analysis.ru/")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--query", help="Фильтр по запросу")
    parser.add_argument(
        "--dimensions", nargs="+", default=["query", "page", "date"],
        choices=["query", "page", "country", "device", "date"],
    )
    parser.add_argument("--format", choices=["csv", "json", "both"], default="both")
    args = parser.parse_args()

    if args.days < 1:
        print(f"❌ --days должен быть >= 1, получено: {args.days}")
        sys.exit(1)

    rows, dimensions, is_partial = fetch_search_analytics(
        site_url=args.site, days=args.days,
        query_filter=args.query, dimensions=args.dimensions,
    )

    if not rows:
        print("⚠️  Нет данных за указанный период")
        return

    # Timestamp with time to avoid collisions on repeated runs
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = "_partial" if is_partial else ""
    base = f"search_data_{timestamp}{suffix}"

    if args.format in ("csv", "both"):
        save_to_csv(rows, dimensions, f"{base}.csv")
    if args.format in ("json", "both"):
        save_to_json(rows, dimensions, f"{base}.json")
    print_top_entries(rows, dimensions)

    if is_partial:
        print("❌ Данные неполные — завершаем с ошибкой")
        sys.exit(1)


if __name__ == "__main__":
    main()
