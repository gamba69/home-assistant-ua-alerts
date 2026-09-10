# Testing and release checks

## Local regression suite

Run from the repository root:

```bash
python -m pip install -r requirements_test.txt
pytest -q
python -m compileall -q custom_components tests scripts
```

The test stack is pinned to Home Assistant `2026.9.1` and `pytest-homeassistant-custom-component==0.13.364`. CI uses Python 3.14.

## Test layers

The repository contains pure tests that do not require a running Home Assistant instance and HA integration tests that exercise Config Entry setup, entity registry behavior and lifecycle details when the Home Assistant test package is installed.

Key regression areas include:

- one shared polling runtime and serialized HTTP fetches;
- stale/recovery semantics and failure retention;
- source-schema validation and level precedence;
- administrative inheritance and partial/mixed parent coverage;
- threat de-duplication and unknown-code preservation;
- alert/threat latency baselines, persistence and restart behavior;
- full territory catalog/search/tree navigation;
- short UID-based entity IDs and safe legacy migration;
- EN/RU/UK translation structure;
- HACS/repository contract files.

## GitHub Actions

Three workflows mirror the repository policy used by the companion Vacuum Schedule project:

- `hacs.yaml` — HACS integration validation on pushes, tags, pull requests, releases and manual runs;
- `hassfest.yaml` — Hassfest validation on pushes, tags, pull requests, releases, manual runs and a daily schedule;
- `tests.yaml` — regression tests, Python compilation, JSON/YAML validation and generated-patch rejection.

## Release checklist

Before publishing a release:

1. Confirm `const.py`, `manifest.json`, root README and changelog all refer to the intended version.
2. Run the regression suite and compilation checks.
3. Parse every committed JSON/YAML file.
4. Ensure no `__pycache__`, `.pytest_cache`, `*.pyc`, ZIP or generated patch files are committed.
5. Push to `main` and wait for **Project tests**, **Validate with hassfest** and **HACS validation** to pass.
6. Create a GitHub release whose tag and name are the exact semantic version, e.g. `0.1.16`.

A local environment without the Home Assistant package may skip the HA-dependent test module. Such a skip must not be presented as a full HA E2E pass; GitHub CI installs the pinned test dependencies and is the authoritative public validation run.
