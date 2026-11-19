# Как выложить проект на GitHub

Инструкция для Windows. Git в системе пока не установлен, поэтому первый раздел — установка.

> **Перед публикацией:** репозиторий с медицинским приложением лучше делать **приватным**. В коде нет реальных медицинских данных, но не добавляйте в репозиторий `.env`, `*.db`, папку `.data/` и любые настоящие документы пациентов.

## Быстрый вариант для текущего окружения

Репозиторий на GitHub уже создан. Вставьте свой URL вместо `<URL_РЕПОЗИТОРИЯ>`.

```powershell
$gitDir = 'C:\Users\Dimka\AppData\Local\Temp\opencode\portable_git2\bin'
$env:PATH = "$gitDir;$env:PATH"

cd "C:\Users\Dimka\Documents\Проект по умолчанию"

git init -b main
git config user.name "Ваше Имя"
git config user.email "ваш-github-email@example.com"

git add .
git commit -m "МедАрхив: локально-первое Flutter MVP и серверный прототип"

git remote add origin <URL_РЕПОЗИТОРИЯ>
git push -u origin main
```

Если при создании репозитория на GitHub вы добавили README или `.gitignore`, перед `push` выполните:

```powershell
git pull --rebase origin main
git push -u origin main
```

При первом `push` откроется окно авторизации GitHub. Если его не появилось, используйте Personal Access Token вместо пароля: **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**, права `repo`.

После успешного push проверьте, что в репозитории есть `README.md`, `PROGRESS.md`, `apps/`, `docs/`, `infra/`, `scripts/`, `.github/`.

---

## 1. Установить Git

Вариант А — через winget (Windows 10/11):

```powershell
winget install --id Git.Git -e --source winget
```

Вариант Б — скачать установщик: <https://git-scm.com/download/win> и установить со стандартными настройками.

После установки **закрыть и открыть терминал заново**, затем проверить:

```powershell
git --version
```

Ожидается что-то вроде `git version 2.4x.x`.

Если `git` всё равно не найден — перезагрузить компьютер или добавить `C:\Program Files\Git\cmd` в `PATH`.

---

## 2. Настроить Git (один раз)

```powershell
git config --global user.name "Ваше Имя"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main
```

Email лучше использовать тот же, что на GitHub.

---

## 3. Создать локальный репозиторий

Открыть PowerShell в папке проекта:

```powershell
cd "C:\Users\Dimka\Documents\Проект по умолчанию"
```

Проверить, что `.gitignore` исключает лишнее:

```powershell
git init
git status
```

В списке файлов **не должно быть**:

- `.env`
- `*.db`, `*.sqlite`
- `.data/`
- `__pycache__/`, `.pytest_cache/`
- `migration_test.db`

Если что-то из этого попало — проверить `.gitignore` перед коммитом.

Первый коммит:

```powershell
git add .
git commit -m "МедАрхив: серверный контур почты (auth, mail ingest, inbox, documents)"
```

---

## 4. Создать репозиторий на GitHub

1. Открыть <https://github.com/new>.
2. **Repository name:** например `medarchive`.
3. **Visibility:** `Private` (рекомендуется).
4. **Не** ставить галочки `Add a README file`, `Add .gitignore`, `Choose a license` — они уже есть локально, иначе будет конфликт при первом push.
5. Нажать **Create repository**.

GitHub покажет команды. Нужны только две последние:

```powershell
git remote add origin https://github.com/<ваш-логин>/medarchive.git
git push -u origin main
```

---

## 5. Авторизация при push

При первом `git push` Git попросит войти.

- Откроется окно **Git Credential Manager** → «Sign in with your browser» → войти в GitHub → разрешить доступ.
- Либо вручную: **Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token**, права `repo`. В качестве пароля вставить этот токен.

Токен нигде не публиковать и не коммитить.

После успешного push открыть страницу репозитория — там должны появиться `README.md`, `PROGRESS.md`, `apps/`, `docs/`, `infra/`, `scripts/`, `.github/`.

---

## 6. Альтернатива: GitHub Desktop (без командной строки)

Если не хочется работать с терминалом:

1. Установить <https://desktop.github.com/>.
2. `File → Add local repository` → выбрать папку проекта.
3. Если Git ещё не инициализирован, GitHub Desktop предложит создать репозиторий — согласиться.
4. Ввести сообщение коммита → **Commit to main**.
5. **Publish repository** → выбрать имя и `Keep this code private`.

---

## 7. Проверка после публикации

- Открыть вкладку **Actions** — workflow `ci` должен запуститься автоматически и прогнать `pytest` (35 тестов).
- Если CI упал, открыть лог: чаще всего причина — забытая зависимость в `requirements.txt`.
- В **Settings → Secrets and variables → Actions** ничего добавлять не нужно: тесты используют SQLite и локальное хранилище.

---

## 8. Дальнейший рабочий цикл

```powershell
# посмотреть изменения
git status

# добавить и закоммитить
git add .
git commit -m "T5.7: IMAP-коннектор"

# отправить на GitHub
git push
```

Полезно:

```powershell
git log --oneline -10      # последние коммиты
git diff                   # что изменилось, но ещё не добавлено
git restore <файл>         # отменить правки в файле
```

---

## 9. Что делать, если...

**`git: command not found`** — Git не в `PATH`. Перезапустить терминал, затем компьютер. Проверить `C:\Program Files\Git\cmd\git.exe`.

**`remote origin already exists`** — удалить старый и добавить новый:

```powershell
git remote remove origin
git remote add origin https://github.com/<логин>/medarchive.git
```

**`failed to push some refs` / `rejected`** — на GitHub уже есть коммиты (например, создали README при создании репозитория). Вариант для пустого проекта:

```powershell
git pull --rebase origin main
git push -u origin main
```

**Случайно закоммитили `.env` или базу** — недостаточно удалить файл новым коммитом, он останется в истории. Проще всего:

```powershell
git rm --cached .env
git rm --cached apps/api/medarchive.db
git commit -m "Убрать локальные файлы из репозитория"
```

Если секреты уже ушли на GitHub — сменить пароли/ключи и при необходимости пересоздать репозиторий с чистой историей.

**Файл больше 100 МБ** — GitHub отклонит push. Проверить:

```powershell
git ls-files | ForEach-Object { if ((Get-Item $_).Length -gt 50MB) { $_ } }
```

Тяжёлые модели OCR и тестовые PDF в репозиторий не класть: для них позже будет отдельное хранилище.
