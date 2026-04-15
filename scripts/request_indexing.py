"""
Запрос индексации URL через Google Indexing API.
Ротация: каждый запуск обрабатывает следующую порцию URL.

Использование:
    python scripts/request_indexing.py --urls all_urls.txt
    python scripts/request_indexing.py --url https://systems-analysis.ru/page.html
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone

from common import get_credentials
from googleapiclient.discovery import build

DAILY_LIMIT = 200
SCOPES = ["https://www.googleapis.com/auth/indexing"]
DATA_DIR = "data_indexing"
STATE_FILE = "data_indexing/indexing_state.json"


def load_urls_from_file(filepath):
    with open(filepath, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_offset": 0, "last_run": None, "total_processed": 0}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_batch(urls, batch_size):
    state = load_state()
    offset = state["last_offset"]
    total = len(urls)

    if offset >= total:
        offset = 0

    end = min(offset + batch_size, total)
    batch = urls[offset:end]

    print(f"📋 Ротация: URL {offset + 1}–{end} из {total}")
    if offset == 0:
        print(f"   🔄 Новый цикл")

    state["last_offset"] = end if end < total else 0
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["total_processed"] = state.get("total_processed", 0) + len(batch)
    state["cycle_position"] = f"{end}/{total}"
    save_state(state)

    return batch


def request_indexing(urls, action="URL_UPDATED"):
    credentials = get_credentials(SCOPES)
    service = build("indexing", "v3", credentials=credentials)

    os.makedirs(DATA_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(DATA_DIR, f"indexing_{timestamp}.json")

    results = []
    success_count = 0
    error_count = 0

    print(f"\n🚀 Отправка {len(urls)} URL на индексацию ({action})...\n")

    for i, url in enumerate(urls, 1):
        try:
            body = {"url": url, "type": action}
            response = service.urlNotifications().publish(body=body).execute()
            result = {
                "url": url,
                "status": "success",
                "notifyTime": response.get("urlNotificationMetadata", {}).get(
                    "latestUpdate", {}
                ).get("notifyTime", ""),
            }
            success_count += 1
            print(f"  ✅ [{i}/{len(urls)}] {url}")
        except Exception as e:
            error_msg = str(e)
            result = {"url": url, "status": "error", "error": error_msg}
            error_count += 1
            print(f"  ❌ [{i}/{len(urls)}] {url}")
            print(f"      {error_msg[:100]}")

        results.append(result)
        if i < len(urls):
            time.sleep(0.5)

    log_data = {
        "timestamp": timestamp,
        "action": action,
        "total": len(urls),
        "success": success_count,
        "errors": error_count,
        "results": results,
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    print(f"\n📊 Результат: {success_count} ✅ / {error_count} ❌")
    print(f"📝 Лог: {log_file}")
    return log_data


def main():
    parser = argparse.ArgumentParser(description="Запрос индексации URL в Google")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Один URL для индексации")
    group.add_argument("--urls", help="Файл со списком URL")
    parser.add_argument(
        "--action",
        choices=["URL_UPDATED", "URL_DELETED"],
        default="URL_UPDATED",
    )
    parser.add_argument("--batch-size", type=int, default=DAILY_LIMIT)
    parser.add_argument("--no-rotate", action="store_true")
    args = parser.parse_args()

    if args.url:
        request_indexing([args.url], action=args.action)
    else:
        all_urls = load_urls_from_file(args.urls)
        if args.no_rotate:
            batch = all_urls[: args.batch_size]
        else:
            batch = get_batch(all_urls, args.batch_size)
        request_indexing(batch, action=args.action)


if __name__ == "__main__":
    main()
