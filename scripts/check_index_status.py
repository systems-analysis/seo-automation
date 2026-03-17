"""
Проверка статуса индексации URL через URL Inspection API.

Использование:
    python scripts/check_index_status.py --url https://systems-analysis.ru/page.html
    python scripts/check_index_status.py --urls urls.txt
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/webmasters"]
DATA_DIR = "data_index_status"


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


def check_url_status(service, url, site_url):
    try:
        request = {"inspectionUrl": url, "siteUrl": site_url}
        response = service.urlInspection().index().inspect(body=request).execute()
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
        }
    except Exception as e:
        return {"url": url, "status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Проверка статуса индексации URL")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="URL для проверки")
    group.add_argument("--urls", help="Файл со списком URL")
    parser.add_argument("--site", default="https://systems-analysis.ru/")
    args = parser.parse_args()

    credentials = get_credentials()
    service = build("searchconsole", "v1", credentials=credentials)

    if args.url:
        urls = [args.url]
    else:
        with open(args.urls, "r") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    print(f"🔍 Проверка статуса индексации: {len(urls)} URL\n")

    results = []
    for i, url in enumerate(urls, 1):
        result = check_url_status(service, url, args.site)
        results.append(result)
        if result["status"] == "success":
            verdict_icon = "✅" if result["verdict"] == "PASS" else "⚠️"
            print(f"  {verdict_icon} [{i}/{len(urls)}] {url}")
            print(f"      Индексация: {result['indexingState']}")
            print(f"      Покрытие: {result['coverageState']}")
            print(f"      Последнее сканирование: {result['lastCrawlTime']}")
        else:
            print(f"  ❌ [{i}/{len(urls)}] {url}")
            print(f"      {result['error'][:100]}")
        if i < len(urls):
            time.sleep(1)

    os.makedirs(DATA_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(DATA_DIR, f"index_status_{timestamp}.json")
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n📝 Лог: {log_file}")


if __name__ == "__main__":
    main()
