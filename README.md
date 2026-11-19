# МедАрхив

Кроссплатформенное приложение для сбора и каталогизации медицинских документов: анализов, заключений, описаний исследований и записей о приёмах врача.

Ключевое ограничение проекта: **распознавание выполняется полностью на устройстве**, без внешних AI-API и генеративных моделей.

## Текущий статус

**Направление изменено на локально-первое MVP.** Основной продукт — Flutter-приложение: импорт документов из галереи и файлов, хранение и OCR полностью на устройстве. Обязательного сервера нет.

- Flutter-клиент: web-прототип собран и визуально проверен; импорт/список/карточка/удаление и демо-данные работают.
- Backend в `apps/api` — **прототип и референс**, не часть MVP-поставки.
- Распознавание: Tesseract, локально, без облачных AI.
- Supabase — только необязательный бэкап; Vercel в MVP не используется.
- Целевая аудитория — Россия: без Firebase, Google Play Payments и платных SDK.

Серверный прототип, который уже работает:

- регистрация, вход, refresh-ротация, JWT;
- уникальный forward-адрес для каждого пользователя;
- SMTP-приёмник писем, разбор MIME, скачивание вложений;
- дедупликация писем и вложений;
- фильтры релевантности: allow/deny по домену, ключевому слову и MIME;
- IMAP-коннектор: app password, incremental-синхронизация по UID;
- inbox API для устройства: список, claim, complete, скачивание файла;
- загрузка документов с результатом локального распознавания;
- миграции Alembic, 35 passing tests.

Подробности — в [PROGRESS.md](PROGRESS.md) и [docs/adr/003-local-first-gallery.md](docs/adr/003-local-first-gallery.md).

## Структура

```
apps/api/          FastAPI-прототип: auth, mail ingest, inbox, documents
apps/mobile/       Flutter-клиент: локальное хранение, OCR, галерея
infra/             docker-compose для прототипа (в MVP не требуется)
scripts/           запуск прототипа, тесты, smoke, демо-данные
docs/adr/          архитектурные решения
docs/russia-constraints.md  ограничения сервисов для РФ
fixtures/          синтетические документы (пока не добавлены)
ПЛАН_РАЗРАБОТКИ.md Полный план на 10 этапов
PROGRESS.md        Журнал прогресса и следующие шаги
```

## Быстрый старт

Требуется Python 3.12. В текущем окружении используется портативный интерпретатор, скрипты находят его автоматически.

### Тесты

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
```

### Сквозной smoke

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
```

Поднимает API и SMTP, прогоняет полный сценарий письма и останавливает процессы.

### API

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_api.ps1
```

Swagger: http://127.0.0.1:8000/docs

### SMTP-приёмник

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_smtp.ps1
```

Проверка полного сценария:

1. Зарегистрироваться и создать forward-адрес:
   `POST /v1/auth/register`, затем `POST /v1/mail/accounts`.
2. Отправить письмо:
   ```powershell
   python scripts/send_test_email.py --to u-<token>@in.medarchive.local
   ```
3. Посмотреть inbox:
   `GET /v1/inbox` с Bearer-токеном.
4. Забрать вложение: `GET /v1/inbox/{id}/file`.
5. Подтвердить обработку: `POST /v1/inbox/{id}/claim`, затем `POST /v1/inbox/{id}/complete`.

### Flutter-клиент (локальное MVP)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_mobile.ps1 -Target web
```

Скрипт добавляет портативный Git и Flutter SDK в `PATH`. Для визуальной проверки без запуска Chrome можно собрать статическую web-версию:

```powershell
$env:PATH = 'C:\Users\Dimka\AppData\Local\Temp\opencode\portable_git2\bin;' + $env:PATH
$env:FLUTTER_ROOT = 'C:\Users\Dimka\AppData\Local\Temp\opencode\flutter_sdk\flutter'
cd apps\mobile
& "$env:FLUTTER_ROOT\bin\flutter.bat" build web --no-wasm-dry-run
& "C:\Users\Dimka\AppData\Local\Temp\opencode\python312\python.exe" -m http.server 8080 --bind 127.0.0.1
```

Затем открыть `http://localhost:8080/`.

### Docker Compose

```bash
cd infra
docker compose up --build
```

Поднимает Postgres, Valkey, MinIO, API (порт 8000) и SMTP (порт 8025). Миграции применяются при старте API.

## Документация

- [ПЛАН_РАЗРАБОТКИ.md](ПЛАН_РАЗРАБОТКИ.md) — продукт, архитектура, этапы, критерии приёмки.
- [PROGRESS.md](PROGRESS.md) — что сделано, как проверено, что дальше.
- [docs/adr](docs/adr) — принятые архитектурные решения.
- [docs/adr/003-local-first-gallery.md](docs/adr/003-local-first-gallery.md) — локально-первое MVP.
- [docs/russia-constraints.md](docs/russia-constraints.md) — какие сервисы доступны в РФ.
- [docs/imap-setup.md](docs/imap-setup.md) — подключение ящика по IMAP (для прототипа).
- [docs/github-upload.md](docs/github-upload.md) — как выложить проект на GitHub и настроить CI.
