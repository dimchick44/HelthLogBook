# МедАрхив — мобильный клиент

Локально-первое Flutter-приложение: импорт документов из галереи и файлов,
хранение на устройстве, распознавание текста без сети и облачных сервисов.

## Запуск

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_mobile.ps1 -Target web
```

Для Android:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_mobile.ps1 -Target android
```

Flutter SDK установлен в `C:\Users\Dimka\AppData\Local\Temp\opencode\flutter_sdk\flutter`.
Портативный Git — в `C:\Users\Dimka\AppData\Local\Temp\opencode\portable_git`.

## Структура

```
lib/
  app.dart                    Маршрутизация и тема
  main.dart                   Точка входа
  data/database.dart          Drift-схема: документы
  providers/
    app_providers.dart        Доступ к БД и списку документов
    import.dart               Импорт из галереи/файлов
  screens/
    documents_screen.dart     Список документов
    document_detail_screen.dart  Карточка документа
    settings_screen.dart      Настройки и приватность
  theme/app_theme.dart        Material 3 тема
```

## Текущее состояние

- Material 3, русская локаль, тёмная тема по системной настройке.
- Список документов, карточка, экран настроек.
- Веб-режим показывает демо-данные для визуальной проверки.
- Нативный режим копирует выбранные файлы в приватную папку и пишет метаданные в Drift.
- OCR и классификация — следующий шаг.
