"""Генерация отчёта по результатам проверки индексации."""

import json
import glob
import os

DATA_DIR = "data"
LOG_DIR = "logs"


def main():
    files = sorted(glob.glob(os.path.join(LOG_DIR, "index_status_*.json")))
    if not files:
        print("Нет файлов статуса индексации")
        return

    latest = files[-1]
    with open(latest) as f:
        data = json.load(f)

    indexed = [r for r in data if r.get("verdict") == "PASS"]
    not_indexed = [
        r for r in data if r.get("status") == "success" and r.get("verdict") != "PASS"
    ]
    errors = [r for r in data if r.get("status") == "error"]

    print("=== ОТЧЁТ ПО ИНДЕКСАЦИИ ===")
    print(f"Всего проверено: {len(data)}")
    print(f"✅ Проиндексировано: {len(indexed)}")
    print(f"⚠️  Не проиндексировано: {len(not_indexed)}")
    print(f"❌ Ошибки проверки: {len(errors)}")
    print()

    if not_indexed:
        print("--- Не проиндексированные страницы ---")
        for r in not_indexed:
            print(f"  {r['url']}")
            print(f"    Причина: {r.get('coverageState', 'N/A')}")
            print(f"    Статус: {r.get('indexingState', 'N/A')}")
            print()

    if errors:
        print("--- Ошибки проверки ---")
        for r in errors:
            print(f"  {r['url']}")
            print(f"    Ошибка: {r.get('error', 'N/A')[:100]}")
            print()

    # Сохраняем отчёт в Markdown
    os.makedirs(DATA_DIR, exist_ok=True)
    report_path = os.path.join(DATA_DIR, "index_report.md")
    basename = os.path.basename(latest).replace("index_status_", "").replace(".json", "")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Отчёт по индексации\n\n")
        f.write(f"Дата проверки: {basename}\n\n")
        f.write("| Метрика | Значение |\n|---------|----------|\n")
        f.write(f"| Всего проверено | {len(data)} |\n")
        f.write(f"| ✅ Проиндексировано | {len(indexed)} |\n")
        f.write(f"| ⚠️ Не проиндексировано | {len(not_indexed)} |\n")
        f.write(f"| ❌ Ошибки | {len(errors)} |\n\n")

        if indexed:
            f.write("## ✅ Проиндексированные страницы\n\n")
            for r in indexed:
                f.write(f"- {r['url']}\n")
                f.write(f"  - Последнее сканирование: {r.get('lastCrawlTime', 'N/A')}\n")
            f.write("\n")

        if not_indexed:
            f.write("## ⚠️ Не проиндексированные страницы\n\n")
            for r in not_indexed:
                f.write(f"- **{r['url']}**\n")
                f.write(f"  - Причина: {r.get('coverageState', 'N/A')}\n")
                f.write(f"  - Статус: {r.get('indexingState', 'N/A')}\n")
            f.write("\n")

        if errors:
            f.write("## ❌ Ошибки\n\n")
            for r in errors:
                f.write(f"- {r['url']}: {r.get('error', 'N/A')[:100]}\n")

    print(f"📄 Отчёт сохранён: {report_path}")


if __name__ == "__main__":
    main()
