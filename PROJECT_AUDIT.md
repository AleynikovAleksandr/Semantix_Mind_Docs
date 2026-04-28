# Аудит проекта Semantix_Mind_Docs

Дата аудита: 2026-04-28

## Что проверено
- Запуск unit/integration-тестов через `pytest`.
- Проверка импортов/синтаксиса через `python -m compileall backend worker tests`.
- Быстрый обзор архитектуры backend/worker и схем API.

## Найденные проблемы

### 1) Тесты не запускаются без `aiosqlite`
**Симптом:** `ModuleNotFoundError: No module named 'aiosqlite'` при старте `tests/conftest.py`.

**Причина:** тестовая БД использует `sqlite+aiosqlite`, но зависимость отсутствует в среде.

**Рекомендация:**
- добавить `aiosqlite` в dev/test зависимости,
- в CI запускать тесты в окружении с установленными test-зависимостями.

### 2) Локальный запуск тестов требовал ручного `PYTHONPATH`
**Симптом:** `ModuleNotFoundError: No module named 'app'` при запуске pytest из корня репозитория.

**Исправлено:** добавлен `pytest.ini` c `pythonpath = backend`.

### 3) Мутабельные значения по умолчанию в Pydantic-схемах
**Риск:** поля-списки с `=[]` могут вести к нежелательному разделению состояния между экземплярами.

**Исправлено:** в `backend/app/schemas/document.py` используется `Field(default_factory=list)` для `themes` и `segments`.

## Что стоит улучшить дополнительно

1. **Документация**
   - Сейчас `README.md` практически пуст.
   - Добавить: архитектуру, инструкции запуска, env-переменные, workflow миграций и тестирования.

2. **Качество и CI**
   - Добавить отдельные команды для: lint (`ruff`), format (`black`), type-check (`mypy`/`pyright`).
   - Настроить CI (GitHub Actions): install deps → migrate test DB → pytest.

3. **Надёжность фоновой обработки**
   - Вынести ресурсозатратные шаги OCR/NLP в отдельные тесты с моками.
   - Добавить smoke-тест пайплайна Celery с фиктивным документом.

4. **Безопасность/конфигурация**
   - Исключить insecure defaults в проде (например, `JWT_SECRET_KEY: change-me`) и валидировать обязательные секреты при старте.

