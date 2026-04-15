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

    # Cycle status
    cycle_state = load_cycle_state()
    if cycle_state:
        cycle_pos = cycle_state.get("cycle_position", "N/A")
        print(f"📋 Цикл: {cycle_pos}")
        print(f"   Последний запуск: {cycle_state.get('last_run', 'N/A')}")


if __name__ == "__main__":
    main()
