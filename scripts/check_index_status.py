"""
Проверка статуса индексации URL через URL Inspection API.

Поддерживает ротацию по батчам (как request_indexing.py):
- Лимит API: 2000 запросов/день на property
- Batch size: 1800 (с запасом)
- Состояние сохраняется ПОСЛЕ обработки (не до)
- При quota-429 — немедленная остановка + checkpoint
- SSL/timeout — retry с exponential backoff
- При смене sitemap mid-cycle — сброс курсора

Использование:
    python scripts/check_index_status.py --urls urls.txt
    python scripts/check_index_status.py --urls urls.txt --batch-size 1800
    python scripts/check_index_status.py --url https://systems-analysis.ru/page.html
"""

import argparse
import hashlib
import json
import os
import random
import ssl
import socket
import sys
import time
from datetime import datetime, timezone

from common import get_credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/webmasters"]
DATA_DIR = "data_index_status"
STATE_FILE = "data_index_status/inspection_state.json"
DAILY_LIMIT = 1800
RATE_LIMIT_SLEEP = 0.2
MAX_RETRIES = 3


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print("⚠️  Повреждённый state-файл, начинаем с нуля")
    return {
        "last_offset": 0,
        "last_run": None,
        "total_processed": 0,
        "manifest_hash": None,
        "cycle_started": None,
        "cycle_position": "0/0",
    }


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_and_lock_manifest(filepath):
    """Load URL list, deduplicate, sort deterministically, compute hash."""
    with open(filepath, "r", encoding="utf-8") as f:
        urls = sorted(set(
            line.strip() for line in f if line.strip() and not line.startswith("#")
        ))
    manifest_hash = hashlib.sha256("\n".join(urls).encode()).hexdigest()[:16]
    return urls, manifest_hash


def compute_batch(urls, manifest_hash, batch_size):
    """Compute next batch WITHOUT persisting state. Caller saves after processing.

    Returns:
        (batch, start_offset, is_new_cycle)
    """
    state = load_state()
    offset = state["last_offset"]
    total = len(urls)

    # Manifest changed mid-cycle → reset cursor for full coverage guarantee
    old_hash = state.get("manifest_hash")
    if old_hash and old_hash != manifest_hash and offset > 0:
        print(f"⚠️  Sitemap изменился (hash: {old_hash} → {manifest_hash})")
        print(f"   Сбрасываем курсор для полного покрытия")
        offset = 0

    if offset >= total:
        offset = 0

    end = min(offset + batch_size, total)
    batch = urls[offset:end]
    is_new_cycle = (offset == 0)

    print(f"📋 Ротация: URL {offset + 1}–{end} из {total}")
    if is_new_cycle:
        print(f"   🔄 Новый цикл")

    return batch, offset, is_new_cycle


def check_url_status(service, url, site_url, max_retries=MAX_RETRIES):
    """Check single URL index status with retry and quota detection.

    Returns:
        (result_dict, should_stop): should_stop=True on daily quota exhaustion.
    """
    request = {"inspectionUrl": url, "siteUrl": site_url}

    for attempt in range(max_retries + 1):
        try:
            response = (
                service.urlInspection()
                .index()
                .inspect(body=request)
                .execute(num_retries=0)
            )
            result = response.get("inspectionResult", {})
            index_status = result.get("indexStatusResult", {})
            return {
                "url": url,
                "verdict": index_status.get("verdict", "N/A"),
                "coverageState": index_status.get("coverageState", "N/A"),
                "indexingState": index_status.get("indexingState", "N/A"),
                "lastCrawlTime": index_status.get("lastCrawlTime", "N/A"),
                "robotsTxtState": index_status.get("robotsTxtState", "N/A"),
                "pageFetchState": index_status.get("pageFetchState", "N/A"),
                "status": "success",
            }, False

        except HttpError as e:
            status = getattr(e.resp, "status", None) if hasattr(e, "resp") else None
            error_text = str(e)

            # Daily quota exhausted — stop immediately, don't retry
            if status == 429 and "Quota exceeded" in error_text:
                return {
                    "url": url,
                    "status": "quota_exceeded",
                    "error": error_text[:200],
                }, True

            # Server error — retry with backoff
            if status and status >= 500 and attempt < max_retries:
                wait = (2 ** attempt) + random.random()
                print(f"      ⏳ HTTP {status}, retry {attempt + 1}/{max_retries} ({wait:.1f}s)")
                time.sleep(wait)
                continue

            return {"url": url, "status": "error", "error": error_text[:200]}, False

        except (ssl.SSLError, socket.timeout, ConnectionError, OSError) as e:
            if attempt < max_retries:
                wait = (2 ** attempt) + random.random()
                print(f"      ⏳ {type(e).__name__}, retry {attempt + 1}/{max_retries} ({wait:.1f}s)")
                time.sleep(wait)
                continue
            return {"url": url, "status": "error", "error": str(e)[:200]}, False

        except Exception as e:
            return {"url": url, "status": "error", "error": str(e)[:200]}, False

    return {"url": url, "status": "error", "error": "max retries exceeded"}, False


def run_batch_inspection(urls, site_url):
    """Run inspection on a batch of URLs, stop on quota exhaustion.

    Returns:
        (results, actually_processed_count, success_count)
    """
    credentials = get_credentials(SCOPES)
    service = build("searchconsole", "v1", credentials=credentials)

    os.makedirs(DATA_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(DATA_DIR, f"index_status_{timestamp}.json")

    results = []
    success_count = 0
    error_count = 0
    processed = 0

    print(f"\n🔍 Проверка статуса индексации: {len(urls)} URL\n")

    for i, url in enumerate(urls, 1):
        result, should_stop = check_url_status(service, url, site_url)

        if should_stop:
            # Quota exhausted — don't count this URL as processed
            results.append(result)
            print(f"\n🛑 Квота исчерпана на [{i}/{len(urls)}]")
            break

        results.append(result)
        processed += 1

        if result["status"] == "success":
            success_count += 1
            verdict_icon = "✅" if result["verdict"] == "PASS" else "⚠️"
            print(f"  {verdict_icon} [{i}/{len(urls)}] {url}")
            print(f"      Индексация: {result['indexingState']}")
            print(f"      Покрытие: {result['coverageState']}")
        else:
            error_count += 1
            print(f"  ❌ [{i}/{len(urls)}] {url}")
            print(f"      {result.get('error', 'N/A')[:100]}")

        if i < len(urls):
            time.sleep(RATE_LIMIT_SLEEP)

    # Save results
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n📊 Результат: {success_count} ✅ / {error_count} ❌")
    if processed < len(urls):
        print(f"🛑 Остановлено по квоте после {processed} URL")
    print(f"📝 Лог: {log_file}")

    return results, processed, success_count


def main():
    parser = argparse.ArgumentParser(description="Проверка статуса индексации URL")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="URL для проверки")
    group.add_argument("--urls", help="Файл со списком URL")
    parser.add_argument("--site", default="https://systems-analysis.ru/")
    parser.add_argument("--batch-size", type=int, default=DAILY_LIMIT)
    parser.add_argument("--no-rotate", action="store_true")
    args = parser.parse_args()

    if args.url:
        # Single URL mode — no rotation, no state
        credentials = get_credentials(SCOPES)
        service = build("searchconsole", "v1", credentials=credentials)
        result, _ = check_url_status(service, args.url, args.site)

        if result["status"] == "success":
            verdict_icon = "✅" if result["verdict"] == "PASS" else "⚠️"
            print(f"  {verdict_icon} {args.url}")
            print(f"      Индексация: {result['indexingState']}")
            print(f"      Покрытие: {result['coverageState']}")
            print(f"      Последнее сканирование: {result['lastCrawlTime']}")
        else:
            print(f"  ❌ {args.url}")
            print(f"      {result.get('error', 'N/A')[:100]}")
            sys.exit(1)
        return

    # Batch mode
    all_urls, manifest_hash = load_and_lock_manifest(args.urls)

    if args.no_rotate:
        batch = all_urls[: args.batch_size]
        _, processed, success_count = run_batch_inspection(batch, args.site)
        if processed > 0 and success_count == 0:
            sys.exit(1)
        return

    batch, start_offset, is_new_cycle = compute_batch(
        all_urls, manifest_hash, args.batch_size
    )

    results, actually_processed, success_count = run_batch_inspection(batch, args.site)

    # Save state AFTER processing — cursor advances even on all-error batch
    # to avoid deadlocking rotation on a permanently bad slice
    state = load_state()
    effective_pos = start_offset + actually_processed
    if effective_pos >= len(all_urls):
        state["last_offset"] = 0
        state["cycle_position"] = f"{len(all_urls)}/{len(all_urls)}"
    else:
        state["last_offset"] = effective_pos
        state["cycle_position"] = f"{effective_pos}/{len(all_urls)}"
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["total_processed"] = state.get("total_processed", 0) + actually_processed
    state["manifest_hash"] = manifest_hash
    if is_new_cycle:
        state["cycle_started"] = datetime.now(timezone.utc).isoformat()
    save_state(state)

    print(f"\n📌 State сохранён: offset={state['last_offset']}, "
          f"cycle={state['cycle_position']}")

    # Hard failure: exit non-zero AFTER state is saved
    if actually_processed > 0 and success_count == 0:
        print("❌ Все запросы завершились ошибкой")
        sys.exit(1)


if __name__ == "__main__":
    main()
