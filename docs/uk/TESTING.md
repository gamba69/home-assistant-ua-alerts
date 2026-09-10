# Тестування та випуск

## Локальний прогін

З кореня репозиторію:

```bash
python -m pip install -r requirements_test.txt
pytest -q
python -m compileall -q custom_components tests scripts
```

Тестовий стек закріплено на Home Assistant `2026.9.1` і `pytest-homeassistant-custom-component==0.13.364`. CI використовує Python 3.14.

## Що перевіряється

Регресії покривають єдиний polling runtime, відсутність паралельних fetch, stale/recovery, валідацію схеми джерела, пріоритет рівнів, адміністративне успадкування, partial/mixed охоплення, дедуплікацію загроз, невідомі threat-коди, alert/threat latency та їх збереження, довідник/пошук/дерево, короткі entity_id і міграцію старих ID, EN/RU/UK локалізацію та структуру HACS-репозиторію.

## GitHub Actions

За аналогією з Vacuum Schedule використовуються три незалежні workflow:

- `hacs.yaml` — HACS validation;
- `hassfest.yaml` — Hassfest validation, включно зі щоденним scheduled run;
- `tests.yaml` — pytest, compileall, перевірка JSON/YAML і заборона згенерованих `.patch`.

## Чек-лист релізу

1. Звірити версію в `const.py`, `manifest.json`, README та changelog.
2. Запустити pytest і compileall.
3. Перевірити всі JSON/YAML.
4. Не допускати до Git `__pycache__`, `.pytest_cache`, `*.pyc`, ZIP і `.patch`.
5. Після push у `main` дочекатися зелених **Project tests**, **Validate with hassfest**, **HACS validation**.
6. Створити GitHub Release з тегом та назвою точно за SemVer, наприклад `0.1.16`.

Якщо локально пакет Home Assistant не встановлено, HA-залежний модуль може бути пропущено. Такий прогін не є повним HA E2E; публічним підтвердженням слугує CI, який встановлює закріплені залежності.
