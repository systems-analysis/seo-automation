"""
Сбор данных из Google Search Console.

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

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
DATA_DIR = "data_search"


def get_credentials():
    key_env = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
    key_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

    if key_env:
        info = json.loads(key_env)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    elif os.path.exists(key_file):
        return service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
    else:
        print("❌ Ключ сервисного аккаунта не найден.")
        sys.exit(1)


def fetch_search_analytics(site_url, days=7, query_filter=None, dimensions=None):
    credentials = get_credentials()
    service = build("searchconsole", "v1", credentials=credentials)

    end_date = datetime.now(timezone.utc).date() - timedelta(days=3)
    start_date = end_date - timedelta(days=days)

    if dimensions is None:
        dimensions = ["query", "page", "date"]

    request_body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": dimensions,
        "rowLimit": 5000,
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
    print(f"   Период: {start_date} — {end_date}")
    if query_filter:
        print(f"   Фильтр: «{query_filter}»")
    print()

    try:
        response = (
            service.searchanalytics()
            .query(siteUrl=site_url, body=request_body)
            .execute()
        )
    except Exception as e:
        print(f"❌ Ошибка API: {e}")
        sys.exit(1)

    rows = response.get("rows", [])
    print(f"✅ Получено {len(rows)} строк данных\n")
    return rows, dimensions


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


def print_top_queries(rows, limit=20):
    query_data = {}
    for row in rows:
        keys = row.get("keys", [])
        if not keys:
            continue
        query = keys[0]
        if query not in query_data:
            query_data[query] = {"clicks": 0, "impressions": 0, "position_sum": 0, "count": 0}
        query_data[query]["clicks"] += row.get("clicks", 0)
        query_data[query]["impressions"] += row.get("impressions", 0)
        query_data[query]["position_sum"] += row.get("position", 0)
        query_data[query]["count"] += 1

    sorted_queries = sorted(query_data.items(), key=lambda x: x[1]["clicks"], reverse=True)

    print(f"\n{'='*80}")
    print(f" Топ-{limit} запросов по кликам")
    print(f"{'='*80}")
    print(f" {'Запрос':<40} {'Клики':>7} {'Показы':>9} {'Ср.поз.':>8}")
    print(f" {'-'*40} {'-'*7} {'-'*9} {'-'*8}")

    for query, data in sorted_queries[:limit]:
        avg_pos = data["position_sum"] / data["count"] if data["count"] else 0
        q = query[:38] + ".." if len(query) > 40 else query
        print(f" {q:<40} {data['clicks']:>7} {data['impressions']:>9} {avg_pos:>8.1f}")
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

    rows, dimensions = fetch_search_analytics(
        site_url=args.site, days=args.days,
        query_filter=args.query, dimensions=args.dimensions,
    )

    if not rows:
        print("⚠️  Нет данных за указанный период")
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    if args.format in ("csv", "both"):
        save_to_csv(rows, dimensions, f"search_data_{timestamp}.csv")
    if args.format in ("json", "both"):
        save_to_json(rows, dimensions, f"search_data_{timestamp}.json")
    print_top_queries(rows)


if __name__ == "__main__":
    main()
