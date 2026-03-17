"""
Извлечение URL из sitemap (с поддержкой sitemap index).
Используется как вспомогательный скрипт для GitHub Actions.

Использование:
    python scripts/extract_sitemap_urls.py --output urls_list.txt
    python scripts/extract_sitemap_urls.py --sitemap https://example.com/sitemap.xml --output urls.txt
"""

import argparse
import urllib.request
import xml.etree.ElementTree as ET

SITEMAP_URL = "https://systems-analysis.ru/sitemap.xml"
USER_AGENT = "Mozilla/5.0 (compatible; SEOAutomation/1.0; +https://systems-analysis.ru)"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def fetch_xml(url):
    """Загрузить XML с правильным User-Agent."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    response = urllib.request.urlopen(req, timeout=30)
    return ET.parse(response)


def extract_urls(sitemap_url):
    """Извлечь все URL из sitemap (включая sitemap index)."""
    all_urls = []

    print(f"📥 Загрузка: {sitemap_url}")
    tree = fetch_xml(sitemap_url)
    root = tree.getroot()

    # Проверяем: sitemap index или обычный sitemap?
    sub_sitemaps = root.findall(".//sm:sitemap/sm:loc", NS)

    if sub_sitemaps:
        print(f"   Sitemap index: {len(sub_sitemaps)} дочерних sitemap")
        for sub_loc in sub_sitemaps:
            sub_url = sub_loc.text.strip()
            try:
                sub_tree = fetch_xml(sub_url)
                sub_root = sub_tree.getroot()
                urls = [loc.text.strip() for loc in sub_root.findall(".//sm:loc", NS)]
                all_urls.extend(urls)
                print(f"   ✅ {sub_url} → {len(urls)} URL")
            except Exception as e:
                print(f"   ⚠️ {sub_url} → ошибка: {e}")
    else:
        all_urls = [loc.text.strip() for loc in root.findall(".//sm:loc", NS)]
        print(f"   Обычный sitemap: {len(all_urls)} URL")

    return all_urls


def main():
    parser = argparse.ArgumentParser(description="Извлечение URL из sitemap")
    parser.add_argument("--sitemap", default=SITEMAP_URL, help="URL sitemap.xml")
    parser.add_argument("--output", default="_sitemap_urls.txt", help="Файл для сохранения")
    args = parser.parse_args()

    urls = extract_urls(args.sitemap)

    with open(args.output, "w") as f:
        for url in urls:
            f.write(url + "\n")

    print(f"\n💾 Сохранено {len(urls)} URL → {args.output}")


if __name__ == "__main__":
    main()
