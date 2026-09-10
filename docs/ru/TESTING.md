# Тестирование и выпуск

## Локальный прогон

Из корня репозитория:

```bash
python -m pip install -r requirements_test.txt
pytest -q
python -m compileall -q custom_components tests scripts
```

Тестовый стек закреплён на Home Assistant `2026.9.1` и `pytest-homeassistant-custom-component==0.13.364`. CI использует Python 3.13.

## Что проверяется

Регрессии покрывают единый polling runtime, отсутствие параллельных fetch, stale/recovery, валидацию схемы источника, приоритет уровней, административное наследование, partial/mixed охват, дедупликацию угроз, неизвестные threat-коды, alert/threat latency и их сохранение, справочник/поиск/дерево, короткие entity_id и миграцию старых ID, EN/RU/UK локализацию и структуру HACS-репозитория.

## GitHub Actions

По аналогии с Vacuum Schedule используются три независимых workflow:

- `hacs.yaml` — HACS validation;
- `hassfest.yaml` — Hassfest validation, включая ежедневный scheduled run;
- `tests.yaml` — pytest, compileall, проверка JSON/YAML и запрет сгенерированных `.patch`.

## Чек-лист релиза

1. Сверить версию в `const.py`, `manifest.json`, README и changelog.
2. Прогнать pytest и compileall.
3. Проверить все JSON/YAML.
4. Не допускать в Git `__pycache__`, `.pytest_cache`, `*.pyc`, ZIP и `.patch`.
5. После push в `main` дождаться зелёных **Project tests**, **Validate with hassfest**, **HACS validation**.
6. Создать GitHub Release с тегом и именем ровно по SemVer, например `0.1.16`.

Если локально пакет Home Assistant не установлен, HA-зависимый модуль может быть пропущен. Такой прогон нельзя называть полным HA E2E; публичным подтверждением служит CI, который устанавливает закреплённые зависимости.
