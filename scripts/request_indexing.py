"""
Запрос индексации URL через Google Indexing API.

Использование:
    python scripts/request_indexing.py --urls urls.txt
    python scripts/request_indexing.py --sitemap https://systems-analysis.ru/sitemap.xml
    python scripts/request_indexing.py --url https://systems-analysis.ru/page.html
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build

# Лимит Google Indexing API: 200 запросов в день
DAILY_LIMIT = 200
SCOPES = ["https://www.googleapis.com/auth/indexing"]
LOG_DIR = "logs"
USER_AGENT = "Mozilla/5.0 (compatible; SEOAutomation/1.0; +https://systems-analysis.ru)"


def get_credentials():
    """Получить credentials из JSON-ключа (файл или env)."""
    key_env = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
    key_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

    if key_env:
        info = json.loads(key_env)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    elif os.path.exists(key_file):
        return service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
    else:
        print("❌ Ключ сервисного аккаунта не найден.")
        print("   Установите GOOGLE_SERVICE_ACCOUNT_KEY или положите service_account.json")
        sys.exit(1)


def load_urls_from_file(filepath):
    """Загрузить URL из текстового файла (по одному на строку)."""
    with open(filepath, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def fetch_xml(url):
    """Загрузить XML с правильным User-Agent."""
    import urllib.request
    import xml.etree.ElementTree as ET

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    response = urllib.request.urlopen(req, timeout=30)
    return ET.parse(response)


def load_urls_from_sitemap(sitemap_url):
    """Загрузить URL из sitemap.xml (с поддержкой sitemap index)."""
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    all_urls = []

    print(f"📥 Загрузка sitemap: {sitemap_url}")
    tree = fetch_xml(sitemap_url)
    root = tree.getroot()

    # Проверяем: это sitemap index или обычный sitemap?
    sub_sitemaps = root.findall(".//sm:sitemap/sm:loc", ns)

    if sub_sitemaps:
        # Это sitemap index — загружаем каждый дочерний sitemap
        print(f"   Обнаружен sitemap index с {len(sub_sitemaps)} дочерними sitemap")
        for sub_loc in sub_sitemaps:
            sub_url = sub_loc.text.strip()
            print(f"   📥 Загрузка: {sub_url}")
            try:
                sub_tree = fetch_xml(sub_url)
                sub_root = sub_tree.getroot()
                urls = [loc.text.strip() for loc in sub_root.findall(".//sm:loc", ns)]
                all_urls.extend(urls)
                print(f"      Найдено {len(urls)} URL")
            except Exception as e:
                print(f"      ⚠️ Ошибка: {e}")
    else:
        # Обычный sitemap
        all_urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns)]

    print(f"\n   Всего найдено {len(all_urls)} URL в sitemap")
    return all_urls


def request_indexing(urls, action="URL_UPDATED"):
    """
    Отправить запросы на индексацию.

    action: URL_UPDATED | URL_DELETED
    """
    credentials = get_credentials()
    service = build("indexing", "v3", credentials=credentials)

    os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_DIR, f"indexing_{timestamp}.json")

    results = []
    success_count = 0
    error_count = 0

    # Ограничиваем до дневного лимита
    if len(urls) > DAILY_LIMIT:
        print(f"⚠️  {len(urls)} URL превышает лимит ({DAILY_LIMIT}/день).")
        print(f"   Будут обработаны первые {DAILY_LIMIT} URL.")
        urls = urls[:DAILY_LIMIT]

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

        # Небольшая пауза между запросами
        if i < len(urls):
            time.sleep(0.5)

    # Сохраняем лог
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
    group.add_argument("--urls", help="Файл со списком URL (по одному на строку)")
    group.add_argument("--sitemap", help="URL sitemap.xml")
    parser.add_argument(
        "--action",
        choices=["URL_UPDATED", "URL_DELETED"],
        default="URL_UPDATED",
        help="Тип действия (по умолчанию: URL_UPDATED)",
    )

    args = parser.parse_args()

    if args.url:
        urls = [args.url]
    elif args.urls:
        urls = load_urls_from_file(args.urls)
    elif args.sitemap:
        urls = load_urls_from_sitemap(args.sitemap)

    if not urls:
        print("❌ Нет URL для обработки")
        sys.exit(1)

    request_indexing(urls, action=args.action)


if __name__ == "__main__":
    main()
