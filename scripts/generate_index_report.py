"""Генерация отчёта по результатам проверки индексации.

Учитывает цикловую модель проверки: один полный обход сайта
может занимать несколько дней. Отчёт показывает coverage ratio
и статус текущего цикла.
"""

import json
import glob
import os

DATA_DIR = "data_index_status"
STATE_FILE = "data_index_status/inspection_state.json"


def load_cycle_state():
    """Load inspection cycle state if available."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "index_status_*.json")))
    if not files:
        print("Нет файлов статуса индексации")
        return

    latest = files[-1]
    with open(latest) as f:
        data = json.load(f)

    # Filter out quota_exceeded entries — they are not real inspection results
    inspected = [r for r in data if r.get("status") != "quota_exceeded"]

    indexed = [r for r in inspected if r.get("verdict") == "PASS"]
    not_indexed = [
        r for r in inspected if r.get("status") == "success" and r.get("verdict") != "PASS"
    ]
    errors = [r for r in inspected if r.get("status") == "error"]

    print("=== ОТЧЁТ ПО ИНДЕКСАЦИИ ===")
    print(f"Всего в файле: {len(data)} (из них проверено: {len(inspected)})")
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

    # Build markdown report
    os.makedirs(DATA_DIR, exist_ok=True)
    report_path = os.path.join(DATA_DIR, "index_report.md")
    basename = os.path.basename(latest).replace("index_status_", "").replace(".json", "")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Отчёт по индексации\n\n")

        # Cycle status section
        cycle_state = load_cycle_state()
        if cycle_state:
            cycle_pos = cycle_state.get("cycle_position", "N/A")
            parts = cycle_pos.split("/")
            if len(parts) == 2:
                try:
                    done, total = int(parts[0]), int(parts[1])
                    coverage_pct = f"{done / total * 100:.1f}%" if total > 0 else "N/A"
                except ValueError:
                    coverage_pct = "N/A"
            else:
                coverage_pct = "N/A"

            f.write("## Статус цикла проверки\n\n")
            f.write("| Метрика | Значение |\n|---------|----------|\n")
            f.write(f"| Прогресс цикла | {cycle_pos} ({coverage_pct}) |\n")
            f.write(f"| Начало цикла | {cycle_state.get('cycle_started', 'N/A')} |\n")
            f.write(f"| Последний запуск | {cycle_state.get('last_run', 'N/A')} |\n")
            f.write(f"| Всего обработано | {cycle_state.get('total_processed', 'N/A')} |\n")
            f.write(f"| Hash манифеста | `{cycle_state.get('manifest_hash', 'N/A')}` |\n\n")
            if coverage_pct != "100.0%" and coverage_pct != "N/A":
                f.write("> Цикл не завершён. Данные ниже относятся к последнему запуску, "
                        "а не ко всему сайту.\n\n")

        f.write("## Результат последнего запуска\n\n")
        f.write(f"Файл: `{os.path.basename(latest)}`\n\n")
        f.write("| Метрика | Значение |\n|---------|----------|\n")
        f.write(f"| Всего в батче | {len(inspected)} |\n")
        f.write(f"| ✅ Проиндексировано | {len(indexed)} |\n")
        f.write(f"| ⚠️ Не проиндексировано | {len(not_indexed)} |\n")
        f.write(f"| ❌ Ошибки | {len(errors)} |\n")
        if len(inspected) > 0:
            index_rate = len(indexed) / len(inspected) * 100
            f.write(f"| Доля индексации | {index_rate:.1f}% |\n")
        f.write("\n")

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
