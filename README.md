# 🔍 SEO Automation — systems-analysis.ru

Автоматизация SEO-задач через Google Search Console API и Indexing API.

## Возможности

- **Запрос индексации** — отправка URL на индексацию в Google (до 200/день)
- **Сбор аналитики** — клики, показы, позиции, CTR из Search Console
- **Проверка статуса** — проверка индексации конкретных URL
- **Автоматизация** — GitHub Actions с расписанием и ручным запуском

## Быстрый старт

### 1. Настройка Google Cloud

1. Создайте проект в [Google Cloud Console](https://console.cloud.google.com)
2. Включите API:
   - `Google Search Console API`
   - `Web Search Indexing API`
3. Создайте Service Account → скачайте JSON-ключ
4. Добавьте email сервисного аккаунта в [Search Console](https://search.google.com/search-console) как **Владельца**

### 2. Настройка GitHub

1. Склонируйте или форкните этот репозиторий
2. Перейдите в **Settings → Secrets and variables → Actions**
3. Создайте секрет `GOOGLE_SERVICE_ACCOUNT_KEY` — вставьте **содержимое** JSON-файла

### 3. Готово!

Workflows запускаются автоматически или вручную из вкладки **Actions**.

## Скрипты

### Запрос индексации

```bash
# Из sitemap
python scripts/request_indexing.py --sitemap https://systems-analysis.ru/sitemap.xml

# Из файла
python scripts/request_indexing.py --urls urls.txt

# Один URL
python scripts/request_indexing.py --url https://systems-analysis.ru/page.html

# Удаление из индекса
python scripts/request_indexing.py --url https://systems-analysis.ru/old.html --action URL_DELETED
```

### Сбор аналитики Search Console

```bash
# Данные за 7 дней
python scripts/fetch_search_data.py --days 7

# За 30 дней с фильтром по запросу
python scripts/fetch_search_data.py --days 30 --query "системный анализ"

# Только CSV
python scripts/fetch_search_data.py --days 14 --format csv

# Группировка по устройствам
python scripts/fetch_search_data.py --days 7 --dimensions query device
```

### Проверка статуса индексации

```bash
# Один URL
python scripts/check_index_status.py --url https://systems-analysis.ru/page.html

# Список URL
python scripts/check_index_status.py --urls urls.txt
```

## GitHub Actions

| Workflow | Расписание | Описание |
|----------|-----------|----------|
| Request Indexing | Ежедневно 06:00 UTC | Запрос индексации из sitemap |
| Fetch Search Analytics | Пн 07:00 UTC | Сбор аналитики за неделю |

Оба workflow можно запустить вручную из вкладки **Actions** с настраиваемыми параметрами.

## Структура

```
seo-automation/
├── .github/workflows/
│   ├── request_indexing.yml      # Автоиндексация
│   └── fetch_search_data.yml     # Автосбор аналитики
├── scripts/
│   ├── request_indexing.py       # Запрос индексации
│   ├── fetch_search_data.py      # Сбор данных SC
│   └── check_index_status.py     # Проверка статуса
├── data/                         # Аналитика (CSV/JSON)
├── logs/                         # Логи индексации
├── urls.txt                      # Список URL
├── requirements.txt
└── README.md
```

## Лимиты

| API | Лимит |
|-----|-------|
| Indexing API | 200 URL/день |
| URL Inspection API | 2 000 запросов/день |
| Search Analytics API | 25 000 запросов/день |
| GitHub Actions (Free) | 2 000 минут/месяц |

## Локальный запуск

```bash
pip install -r requirements.txt
export GOOGLE_SERVICE_ACCOUNT_FILE=path/to/service_account.json
python scripts/fetch_search_data.py --days 7
```
