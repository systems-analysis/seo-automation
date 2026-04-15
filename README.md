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

## Формат данных

### `data_indexing/indexing_*.json` — логи запросов на индексацию

```json
{
  "timestamp": "20260415_071543",
  "action": "URL_UPDATED",
  "total": 200,
  "success": 200,
  "errors": 0,
  "processed": 200,
  "results": [...]
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `timestamp` | string | Время запуска (UTC), формат `YYYYMMDD_HHMMSS` |
| `action` | string | `URL_UPDATED` — запрос индексации, `URL_DELETED` — удаление |
| `total` | int | Размер батча (сколько URL было запланировано) |
| `success` | int | Успешно отправлено |
| `errors` | int | Ошибки (не считая quota) |
| `processed` | int | Обработано до остановки (может быть < total при quota) |
| `results[]` | array | Результат по каждому URL |

Поля каждого элемента `results[]`:

| Поле | Тип | Описание |
|------|-----|----------|
| `url` | string | URL страницы |
| `status` | string | `success` — отправлено, `error` — ошибка API, `quota_exceeded` — лимит исчерпан |
| `notifyTime` | string | Время уведомления Google (при success), может быть пустым |
| `error` | string | Текст ошибки (при status `error` или `quota_exceeded`) |

### `data_indexing/indexing_state.json` — состояние ротации индексации

```json
{
  "last_offset": 2200,
  "last_run": "2026-04-15T07:15:43.781016+00:00",
  "total_processed": 5655,
  "manifest_hash": "a1b2c3d4e5f67890",
  "cycle_started": "2026-04-01T06:00:00+00:00",
  "cycle_position": "2200/3547"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `last_offset` | int | Начало следующего батча (индекс в отсортированном списке URL) |
| `last_run` | string | ISO 8601 время последнего запуска |
| `total_processed` | int | Всего URL обработано за всё время |
| `manifest_hash` | string | SHA-256 хеш (16 символов) текущего sitemap, для обнаружения изменений |
| `cycle_started` | string | ISO 8601 время начала текущего цикла ротации |
| `cycle_position` | string | Прогресс текущего цикла, формат `offset/total` |

### `data_index_status/index_status_*.json` — результаты проверки индексации

Файл — JSON-массив объектов. Файлы с суффиксом `_partial` содержат неполные данные (остановка по quota).

| Поле | Тип | Описание |
|------|-----|----------|
| `url` | string | URL страницы |
| `status` | string | `success` — данные получены, `error` — ошибка API, `quota_exceeded` — лимит |
| `verdict` | string | Вердикт Google: `PASS` — проиндексирована, `NEUTRAL` / `FAIL` — нет |
| `coverageState` | string | Статус покрытия: `Submitted and indexed`, `Crawled - currently not indexed`, `Discovered - currently not indexed`, `URL is unknown to Google` и др. |
| `indexingState` | string | Состояние индексации: `INDEXING_ALLOWED`, `INDEXING_NOT_ALLOWED` и др. |
| `lastCrawlTime` | string | ISO 8601 время последнего сканирования Googlebot |
| `robotsTxtState` | string | `ALLOWED` — robots.txt разрешает, `DISALLOWED` — запрещает |
| `pageFetchState` | string | `SUCCESSFUL` — страница загружена, `SOFT_404`, `NOT_FOUND`, `SERVER_ERROR` и др. |
| `error` | string | Текст ошибки (только при status `error` или `quota_exceeded`) |

### `data_search/search_data_*.json` — аналитика Search Console

Файл — JSON-массив объектов. Файлы с суффиксом `_partial` содержат неполные данные.

```json
{
  "query": "glm",
  "page": "https://systems-analysis.ru/wiki/GLM_(Zhipu_AI)",
  "date": "2026-04-04",
  "clicks": 5,
  "impressions": 105,
  "ctr": 4.76,
  "position": 4.6
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `query` | string | Поисковый запрос |
| `page` | string | URL страницы |
| `date` | string | Дата (YYYY-MM-DD) |
| `clicks` | int | Количество кликов |
| `impressions` | int | Количество показов в поиске |
| `ctr` | float | Click-through rate в процентах (0–100) |
| `position` | float | Средняя позиция в поиске (1 = первая) |

Набор полей зависит от параметра `--dimensions`. По умолчанию: `query`, `page`, `date`.

### `data_search/search_data_*.csv` — CSV-версия аналитики

Те же данные, что в JSON. Заголовки: `query,page,date,clicks,impressions,ctr,position`.

## Лимиты API

| API | Лимит |
|-----|-------|
| Indexing API | 200 URL/день |
| URL Inspection API | 2 000 запросов/день |
| Search Analytics API | 25 000 запросов/день |
| GitHub Actions (Free) | 2 000 минут/месяц |
