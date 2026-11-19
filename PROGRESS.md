# Журнал разработки

> Обновлено: 2026-11-19
> Текущий этап: **пивот на локально-первое MVP. Основной продукт — Flutter: галерея → локальный OCR. Backend — прототип, не часть поставки.**
> Прогресс MVP: каркас `apps/mobile` запущен и визуально проверен в браузере. Экраны «Документы», карточка, настройки, демо-данные, импорт gallery/files и удаление работают на web-прототипе. `flutter analyze`, `flutter test` и `flutter build web` проходят.
> Временно вместо Drift используется простое локальное хранилище в памяти: кодогенерация Drift сначала не запускалась из-за отсутствия git в PATH. Drift/SQLite вернём отдельным шагом без изменения UI-слоя.
> Следующая сессия: продолжить с раздела 5.0, шаг 3–4: PDF-превью, предобработка и локальный OCR.

---

## 0. Смена направления (важно)

После обсуждения зафиксировано:

- Аудитория — Россия; часть зарубежных сервисов недоступна или требует зарубежную карту.
- Собственный сервер не хостим. Максимум — Supabase и Vercel, и только как опция.
- Распознавание — **полностью на устройстве**, без облачных AI.
- MVP начинается с **галереи и файлов**. Почта (IMAP/пересылка) — следующий этап.
- Flutter-клиент — основной продукт; FastAPI в `apps/api` остаётся прототипом и референсом.

Документы:

- `docs/adr/003-local-first-gallery.md` — архитектура локально-первого MVP.
- `docs/russia-constraints.md` — какие сервисы допустимы.

Всё, что описано ниже в разделах 1–7, относится к **серверному прототипу**. Он рабочий, но не является MVP-поставкой.

---

## 1. Что сделано в этой сессии

### 1.1 Окружение

- Python в системе отсутствовал. Установлен портативный **Python 3.12.8**:
  `C:\Users\Dimka\AppData\Local\Temp\opencode\python312\python.exe`
- В него установлены все зависимости из `apps/api/requirements.txt`.
- `git` и `docker` в системе **отсутствуют** — репозиторий не инициализирован, Docker Compose не проверялся вживую.
- Flutter SDK распакован и используется из:
  `C:\Users\Dimka\AppData\Local\Temp\opencode\flutter_sdk\flutter` (Flutter 3.50.0, Dart 3.14.0).
- Android SDK / эмулятор / MSVC build tools для Windows desktop в этом окружении не настроены (сборка APK и `flutter test` с native assets могут требовать донастройки).
- Node.js есть, но в проекте не используется.

### 1.2 Созданные файлы

```
README.md
ПЛАН_РАЗРАБОТКИ.md            (редакция 2, не менялась в этой сессии)
PROGRESS.md                   (этот файл)
.gitignore

apps/api/
  pyproject.toml
  requirements.txt
  Dockerfile
  .env.example
  alembic.ini
  app/
    main.py                   FastAPI, lifespan, CORS, формат ошибок, /health
    db.py                     async engine, SessionLocal, Base
    models.py                 users, refresh_tokens, consents, mail_accounts,
                              mail_messages, inbox_items, documents, document_files
    schemas.py                Pydantic-схемы
    smtp_server.py            SMTP-приёмник (aiosmtpd), отдельный процесс
    core/config.py            pydantic-settings, префикс MEDARCHIVE_
    core/security.py          scrypt, JWT, refresh-токены
    core/crypto.py            шифрование паролей IMAP (Fernet)
    api/deps.py               Bearer-аутентификация, ошибки
    api/v1/auth.py            register/login/refresh/logout/me
    api/v1/mail.py            forward, IMAP-подключение, sync, правила
    api/v1/inbox.py           список, карточка, файл, claim, complete
    api/v1/documents.py       загрузка, список, карточка, удаление
    api/v1/router.py
    services/storage.py       LocalStorage + S3Storage (boto3), интерфейс Storage
    services/mail_parser.py   MIME-разбор, allowlist, sniffing, дедуп вложений
    services/mail_filters.py  allow/deny правила: domain, keyword, mime
    services/mail_ingest.py   приём письма → mail_messages + inbox_items
    services/imap_sync.py     IMAP-клиент, incremental по UID
  migrations/
    env.py                    async Alembic
    versions/86004279f85c_initial_schema.py
    versions/71945d816003_mail_rules_and_skip_reason.py
    versions/e32871c767b5_imap_accounts.py
  tests/
    conftest.py                фикстуры: SQLite, LocalStorage, AsyncClient
    test_auth.py               5 тестов
    test_mail_ingest.py        6 тестов
    test_mail_filters.py       6 тестов
    test_imap_sync.py          11 тестов
    test_inbox.py              3 теста
    test_documents.py          4 теста

apps/mobile/
  pubspec.yaml                 Flutter-зависимости (локально-первый стек)
  analysis_options.yaml        линт, исключения build/platform
  lib/
    main.dart                  запуск, ProviderScope, инициализация локали
    app.dart                   Material 3, go_router, маршруты
    theme/app_theme.dart       светлая/тёмная тема
    data/database.dart         DocumentRecord + простое локальное хранилище
    providers/app_providers.dart Riverpod: БД, список, карточка, демо-данные
    providers/import.dart      импорт из галереи/файлов, копирование в хранилище
    services/document_store.dart платформенный export хранилища
    services/document_store_io.dart копирование/удаление файлов (native)
    services/document_store_web.dart web-заглушка хранилища
    screens/documents_screen.dart список документов, пустое состояние, импорт
    screens/document_detail_screen.dart превью, метаданные, удаление, заглушка OCR
    screens/settings_screen.dart настройки/приватность
  test/widget_test.dart        smoke-тест оболочки экрана документов
  build/web/                   собранная web-версия для визуальной проверки

infra/docker-compose.yml      Postgres, Valkey, MinIO, API, SMTP
scripts/
  run_api.ps1
  run_smtp.ps1
  test.ps1
  smoke.ps1                   поднимает API+SMTP и гоняет smoke_mail.py
  smoke_mail.py               сквозная проверка: регистрация → письмо → inbox
  send_test_email.py
.github/workflows/ci.yml      pytest на push/PR
docs/adr/
  001-local-recognition.md
  002-mail-forwarding-first.md
  003-local-first-gallery.md
docs/imap-setup.md            подключение ящика по IMAP
docs/russia-constraints.md    ограничения сервисов для РФ
docs/github-upload.md         выгрузка на GitHub и CI
```

### 1.3 Реализованные API

| Метод | Путь | Статус |
|---|---|---|
| POST | `/v1/auth/register` | готово |
| POST | `/v1/auth/login` | готово |
| POST | `/v1/auth/refresh` | готово, с ротацией |
| POST | `/v1/auth/logout` | готово |
| GET | `/v1/auth/me` | готово |
| POST | `/v1/mail/accounts` | готово, идемпотентно |
| POST | `/v1/mail/accounts/imap` | готово, пароль шифруется |
| GET | `/v1/mail/accounts` | готово |
| DELETE | `/v1/mail/accounts/{id}` | готово (soft disable) |
| POST | `/v1/mail/accounts/{id}/sync` | IMAP: реальный опрос по UID; forward: обновляет `last_sync_at` |
| GET | `/v1/mail/accounts/{id}/rules` | готово |
| POST | `/v1/mail/accounts/{id}/rules` | готово, allow/deny |
| DELETE | `/v1/mail/accounts/{id}/rules/{rule_id}` | готово |
| GET | `/v1/inbox` | готово, фильтр по статусу |
| GET | `/v1/inbox/{id}` | готово |
| GET | `/v1/inbox/{id}/file` | готово, Bearer-аутентификация |
| POST | `/v1/inbox/{id}/claim` | готово |
| POST | `/v1/inbox/{id}/complete` | готово |
| POST | `/v1/documents` | готово, multipart + extraction JSON |
| GET | `/v1/documents` | готово |
| GET | `/v1/documents/{id}` | готово |
| DELETE | `/v1/documents/{id}` | готово |
| GET | `/health` | готово |

### 1.4 Проверено

- `python -m compileall app` — без ошибок.
- `pytest -q` — **35 passed** (4.52 с).
- `alembic upgrade head` → `alembic downgrade base` — roundtrip успешен.
- **Сквозной smoke-тест** `scripts/smoke.ps1`: API + SMTP + регистрация + письмо + inbox + скачивание + claim/complete — `SMOKE OK`.
- Пакет установлен в editable-режиме (`pip install -e .`), поэтому `import app` работает из любого каталога.
- Покрытые сценарии:
  - регистрация, логин, неверный пароль, дубль email;
  - refresh-ротация, повторное использование старого refresh → 401;
  - создание forward-адреса, повторный вызов возвращает тот же адрес;
  - приём письма с PDF → inbox item;
  - дубль письма по Message-ID → `duplicate`, второго item нет;
  - неизвестный получатель → `unknown_recipient`;
  - `.exe` отбрасывается, `application/octet-stream` с `%PDF` распознаётся как PDF;
  - claim/complete, повторный claim тем же устройством, конфликт с другим устройством;
  - приватность inbox и документов (чужой пользователь → 404);
  - дедупликация документов по SHA-256;
  - удаление документа;
  - фильтры почты: deny по домену/ключевому слову/MIME, allow-list,
    статус `skipped` с причиной, CRUD правил, приватность правил;
  - IMAP: создание подключения, шифрование пароля, incremental-синхронизация
    по UID, дедупликация, пропуск по правилам, ошибка подключения → 502,
    приватность аккаунта, дубль адреса → 409.

### 1.5 Flutter MVP: визуальная проверка

- Портативный Git распакован во временный каталог:
  `C:\Users\Dimka\AppData\Local\Temp\opencode\portable_git2\bin`.
  `scripts/run_mobile.ps1` обновлён на этот путь.
- `flutter pub get`, `flutter analyze --no-pub` — **No issues found**.
- `flutter test --no-pub` — **1 passed** (smoke-тест экрана документов).
- `flutter build web --no-pub --no-wasm-dry-run` — успешно, артефакт в `apps/mobile/build/web`.
- Web-сборка открыта через локальный HTTP-сервер на `http://localhost:8080/`.
- Скриншот сохранён и открыт в Review pane:
  `C:\Users\Dimka\AppData\Local\Temp\opencode-browser-ssubRa\0\screenshot.png`.
  Ассистент не может напрямую просматривать изображения в этом сеансе, поэтому визуальную оценку делает пользователь.
- В web-режиме показываются три демо-документа; нативный режим копирует выбранные файлы в приватную папку и добавляет запись в хранилище.

---

## 2. Как запустить

### 2.1 Тесты

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
```

Или напрямую:

```powershell
cd apps\api
& "C:\Users\Dimka\AppData\Local\Temp\opencode\python312\python.exe" -m pytest -q
```

### 2.1.1 Сквозной smoke-тест

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
```

Скрипт сам поднимает API и SMTP, регистрирует тестового пользователя, отправляет письмо с PDF, проверяет inbox, скачивание, claim и complete, затем останавливает процессы. Ожидаемый вывод: `SMOKE OK: ...`.

### 2.2 API

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_api.ps1
```

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/docs
- По умолчанию SQLite `apps/api/medarchive.db`, файлы в `apps/api/.data`.

### 2.3 SMTP-приёмник

Отдельный процесс:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_smtp.ps1
```

Слушает `127.0.0.1:8025` (порт задаётся `MEDARCHIVE_SMTP_PORT`).

### 2.4 Ручной сценарий почты

1. Запустить API и SMTP в двух терминалах.
2. Зарегистрироваться:
   ```powershell
   curl.exe -X POST http://127.0.0.1:8000/v1/auth/register -H "Content-Type: application/json" -d "{\"email\":\"test@example.com\",\"password\":\"password123\"}"
   ```
3. Создать адрес:
   ```powershell
   curl.exe -X POST http://127.0.0.1:8000/v1/mail/accounts -H "Authorization: Bearer <access_token>"
   ```
4. Отправить письмо:
   ```powershell
   & "...\python.exe" scripts\send_test_email.py --to u-<token>@in.medarchive.local
   ```
5. Проверить:
   ```powershell
   curl.exe http://127.0.0.1:8000/v1/inbox -H "Authorization: Bearer <access_token>"
   ```

### 2.5 Docker Compose

```bash
cd infra
docker compose up --build
```

Не проверялось: Docker в системе не установлен. При первом запуске проверить:
- миграции применяются командой `alembic upgrade head`;
- bucket `medarchive` создаётся сервисом `minio-init`;
- SMTP и API используют одну БД;
- `MEDARCHIVE_AUTO_CREATE_TABLES=false` в compose (схему создаёт Alembic).

---

## 3. Принятые решения (в этой сессии)

| Решение | Причина |
|---|---|
| Почта через пересылку на `u-<token>@in.<домен>` | нет OAuth-верификации Google, работает с любым ящиком |
| Дедуп писем по `Message-ID`, fallback — SHA-256 сырого письма | повторная пересылка не создаёт дубли |
| Allowlist MIME + sniffing по magic bytes | защита от мусора, при этом PDF в `octet-stream` не теряется |
| Лимит вложения 25 МБ | защита от переполнения, совпадает с планом |
| Вложения хранятся как `users/{user}/mail/{message}/{sha}.{ext}` | дедуп и предсказуемая структура |
| JWT 15 мин + refresh 30 дней, refresh хранится хэшем и ротируется | базовая безопасность |
| Пароли — scrypt (stdlib) | без внешних зависимостей |
| SQLite в dev, PostgreSQL в prod | быстрый старт без Docker |
| LocalStorage в dev, S3/MinIO в prod | один интерфейс `Storage` |
| SMTP — отдельный процесс | не блокирует API, отдельный event loop |
| Файл inbox отдаётся по Bearer, не signed URL | проще для MVP; signed URL — следующая задача |
| `document.type` и `document_date` приходят с устройства в `extraction` | сервер не распознаёт |
| IMAP — app password, пароль шифруется Fernet | OAuth требует верификации; app password работает у большинства провайдеров |
| Incremental-синхронизация по `UID` | повторный опрос не дублирует письма и не перекачивает старые |
| Забор через `BODY.PEEK[]` | письма не помечаются прочитанными |
| Синхронизация в HTTP-запросе, батч 50 | проще для MVP; воркер — следующая задача |

---

## 4. Известные ограничения (важно для следующей сессии)

- **Flutter-клиент не начат.** Нет Flutter SDK. Следующий крупный блок — каркас приложения и экран inbox.
- **IMAP работает только по запросу.** Фонового опроса нет: `sync` вызывается вручную или клиентом. OAuth-провайдеры не поддерживаются, только app password.
- **IMAP-синхронизация синхронная.** Один вызов обрабатывает до `MEDARCHIVE_IMAP_SYNC_LIMIT` писем (50). Для больших ящиков нужен воркер.
- **Ключ шифрования IMAP-паролей.** Если `MEDARCHIVE_SECRET_ENCRYPTION_KEY` не задан, используется JWT_SECRET; его смена ломает сохранённые пароли.
- **Push-уведомлений нет.** Устройство узнаёт о новых вложениях только опросом.
- **Consent API нет.** Модель `Consent` создана, эндпоинтов нет.
- **PATCH документа нет.** Правка полей на сервере пока не поддерживается.
- **Signed URL нет.** Файлы отдаются только с Bearer-токеном.
- **S3-путь не проверен вживую.** Код есть, нужен MinIO/реальный S3.
- **Rate limiting, аудит, удаление аккаунта** не реализованы.
- **Git не инициализирован.** Если появится git — `git init`, первый коммит.
- **Docker Compose не проверен.** Docker отсутствует.
- **Тестовый Python — во временной папке.** Если `C:\Users\Dimka\AppData\Local\Temp\opencode\python312` пропадёт, установить Python 3.12 заново и `pip install -r apps/api/requirements.txt`.
- **`Document.type`** — имя колонки `type`; в PostgreSQL это допустимо, но при сложных запросах помнить про кавычки.
- **SQLite и timezone:** `DateTime(timezone=True)` в SQLite возвращает naive datetime; в коде есть `ensure_aware`, использовать его при сравнениях.
- **SMTP на Windows:** `aiosmtpd` не может стартовать с `hostname=0.0.0.0` (WinError 10049). Локально использовать `127.0.0.1`; в Docker (Linux) `0.0.0.0` работает.
- **Editable install:** выполнен в портативный Python. Если интерпретатор переустановить, повторить `pip install -e apps/api`.
- **Smoke-тест создаёт `apps/api/medarchive.db` и `.data/`.** После проверки их можно удалить.

---

## 5. Следующие задачи (по приоритету)

### 5.0 Flutter MVP: галерея и локальный OCR

1. **Каркас Flutter-приложения — выполнено (web-прототип).**
   - `apps/mobile`, Material 3, Riverpod 3, go_router 17;
   - экраны: «Документы», импорт, карточка документа, настройки;
   - демо-данные для web, простое локальное хранилище и папка файлов, без сети;
   - Drift/SQLite отложен: вернём после настройки кодогенерации.
2. **Импорт из галереи и файлов — выполнено на уровне прототипа.**
   - `image_picker` и `file_picker`;
   - копирование оригинала в приватную папку на native-платформах;
   - список и удаление; миниатюры PDF пока не реализованы.
3. **PDF и изображения.**
   - `pdfrx` для рендера страниц PDF;
   - предобработка: поворот, grayscale, бинаризация.
4. **OCR на устройстве.**
   - Tesseract 5 + `rus.traineddata`;
   - экран результата, ручная правка текста.
5. **Классификация и поля.**
   - тип документа, дата, организация, врач;
   - regex и словари, без генеративных моделей.
6. **Локальный поиск.**
   - по типу, дате, организации, тексту.
7. **Экспорт и бэкап.**
   - ZIP с JSON и оригиналами;
   - опционально Supabase, за флагом.
8. **Android-сборка.**
   - APK, проверка на устройстве 3 ГБ RAM;
   - бюджеты: ≤ 8 с/страница, ≤ 300 МБ RAM.

### 5.1 Backend-прототип (не блокирует MVP)

1. **Push-уведомления (T7.3).**
   - FCM/APNs, токен устройства, уведомление «письмо ждёт обработки».
   - Для РФ: рассмотреть RuStore Push или только локальные уведомления.
2. **Consent API (T2.2).**
   - `GET/POST /v1/consents`, проверка согласия на сканирование почты.
3. **Signed URL / S3 presign (FR-51).**
   - заменить Bearer-скачивание на временные ссылки.
4. **Фоновый IMAP-воркер.**
   - вынести синхронизацию из HTTP-запроса.
5. **Фикстуры для OCR.**
   - 10 синтетических документов + ground truth для golden-тестов.
6. **CI для backend.**
   - GitHub Actions: pytest на push/PR (уже настроен, поддерживать).
7. **Аудит и удаление аккаунта (M7).**

---

## 6. Как продолжить в следующей сессии

1. Прочитать `PROGRESS.md` (этот файл) и при необходимости `ПЛАН_РАЗРАБОТКИ.md`.
2. Проверить окружение:
   ```powershell
   Test-Path "C:\Users\Dimka\AppData\Local\Temp\opencode\python312\python.exe"
   ```
3. Запустить тесты:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/test.ps1
   ```
   Ожидается `35 passed`.
4. Запустить smoke:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
   ```
   Ожидается `SMOKE OK`.
5. Взять первую задачу из раздела 5.
6. После изменений:
   - обновить тесты;
   - обновить этот файл (что сделано, что проверено, что осталось);
   - если менялась схема — создать миграцию Alembic.
7. Не коммитить `.env`, `*.db`, `.data/`, реальные медицинские данные.

---

## 7. Полезные команды

```powershell
# тесты
powershell -ExecutionPolicy Bypass -File scripts/test.ps1

# сквозной smoke (API + SMTP + письмо)
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1

# только один файл
cd apps\api
& "...\python312\python.exe" -m pytest tests/test_mail_ingest.py -q

# миграция
cd apps\api
& "...\python312\python.exe" -m alembic revision --autogenerate -m "change"
& "...\python312\python.exe" -m alembic upgrade head

# запуск API
powershell -ExecutionPolicy Bypass -File scripts/run_api.ps1

# запуск SMTP
powershell -ExecutionPolicy Bypass -File scripts/run_smtp.ps1

# тестовое письмо
& "...\python312\python.exe" scripts/send_test_email.py --to u-<token>@in.medarchive.local
```
