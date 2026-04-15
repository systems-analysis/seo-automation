# 🔍 SEO Automation — systems-analysis.ru

Автоматизация SEO-задач: индексация, проверка статуса, аналитика из Google Search Console.

## Возможности

- **Запрос индексации** — отправка URL на индексацию в Google (до 200/день, с ротацией)
- **Проверка статуса** — проиндексирована страница или нет, причины отказа
- **Сбор аналитики** — клики, показы, позиции, CTR из Search Console
- **Автоматизация** — GitHub Actions по расписанию и ручной запуск

## Структура

```
seo-automation/
├── .github/workflows/
│   ├── request_indexing.yml       # Ежедневная индексация (06:00 UTC)
│   ├── check_index_status.yml     # Проверка индексации (ежедневно 07:37 UTC)
│   └── fetch_search_data.yml      # Сбор аналитики (пн 07:00 UTC)
├── scripts/
│   ├── request_indexing.py        # Запрос индексации + ротация
│   ├── check_index_status.py      # Проверка статуса URL
│   └── fetch_search_data.py       # Сбор данных Search Console
├── data_indexing/                 # Логи запросов на индексацию
├── data_index_status/             # Статусы индексации + отчёты
├── data_search/                   # Аналитика (CSV/JSON)
├── .gitignore
├── requirements.txt
└── README.md
```

## Источник URL

Список страниц берётся из внешнего репозитория:
```
https://raw.githubusercontent.com/systems-analysis/sitemap-data/refs/heads/main/sitemap/sitemap.txt
```

Обновить список — просто обновить файл в `sitemap-data` репо.

## Настройка

### 1. Google Cloud Console

1. Создайте проект → включите API: `Google Search Console API`, `Web Search Indexing API`
2. Создайте Service Account → скачайте JSON-ключ
3. Добавьте email сервисного аккаунта в Search Console как **Владелец**

### 2. GitHub

1. Settings → Secrets → Actions → `GOOGLE_SERVICE_ACCOUNT_KEY` (содержимое JSON)
2. Settings → Actions → General → Workflow permissions: **Read and write**

## Расписание

| Workflow | Расписание | Данные |
|----------|-----------|--------|
| 🔄 Request Indexing | Ежедневно 06:00 UTC | `data_indexing/` |
| 🔍 Check Index Status | Ежедневно 07:37 UTC | `data_index_status/` |
| 📊 Fetch Search Analytics | Понедельник 07:00 UTC | `data_search/` |

Все workflow доступны для ручного запуска из вкладки Actions.

## Ротация индексации

При ~3500 URL и лимите 200/день:
- Каждый день обрабатываются следующие 200 URL
- Полный цикл: ~18 дней
- Состояние хранится в `data_indexing/indexing_state.json`

## Лимиты API

| API | Лимит |
|-----|-------|
| Indexing API | 200 URL/день |
| URL Inspection API | 2 000 запросов/день |
| Search Analytics API | 25 000 запросов/день |
| GitHub Actions (Free) | 2 000 минут/месяц |
