# UA Alerts

UA Alerts is a Home Assistant custom integration for Ukrainian air alerts. It provides
`clear` / `yellow` / `red` alert levels, threat details, administrative coverage,
last-alert history, end-to-end lag measurements, and built-in testing of downstream
automations.

**Current release:** `0.1.25` · **Domain:** `ua_alerts`

**English:** [Documentation](docs/en/README.md) · [Changelog](docs/en/CHANGELOG.md)
**Русский:** [Документация](docs/ru/README.md) · [История изменений](docs/ru/CHANGELOG.md)
**Українська:** [Документація](docs/uk/README.md) · [Історія змін](docs/uk/CHANGELOG.md)

## Highlights

- no API token required;
- one Config Entry per monitored territory, with multiple territories supported at once;
- full bundled Ukrainian administrative catalog: oblasts, raions, hromadas, Kyiv and Sevastopol;
- direct search and hierarchical territory selection;
- `clear`, `yellow`, and `red` alert levels taken from the upstream `alert_level` field;
- correct downward administrative inheritance (`oblast → raion → hromada`) without false upward propagation;
- `none` / `full` / `partial` / `mixed` alert coverage for oblast and raion entries;
- current threat aggregation and de-duplication with stable machine-readable threat codes;
- persisted **Last alert duration** and **Last alert level** for the latest fully observed completed alert;
- compact **Last alert lag** and **Last threat lag** measurements;
- editable global `Poll interval` and `Stale after` entities on every territory device;
- territory-scoped test mode with `Off / Clear / Yellow / Red` and multi-threat selection;
- normal Home Assistant events for alert, threat, and source-availability changes;
- EN / RU / UK localization;
- HACS-ready repository structure and Home Assistant / Hassfest / HACS CI coverage.

## Data source and polling model

UA Alerts reads token-free raw `alerts.in.ua` data through the Ubilling proxy:

`https://ubilling.net.ua/aerialalerts/?source=aiu&raw`

All configured territories share one domain-wide runtime. A normal polling cycle makes
one HTTP request, validates and parses the response once, then updates every configured
territory from the same snapshot. Adding more territories therefore does not multiply
source requests.

Default timing is **3 s polling / 15 s stale**. The values are global for the whole
integration and can be edited directly from any UA Alerts territory device. Polling can
be set to 3–60 seconds; stale to 6–600 seconds and must be at least twice the polling
interval.

A failed request never means `clear`: the last valid snapshot is retained. When the
stale threshold is exceeded, operational entities become unavailable and
`Source available` turns off until valid data returns.

## Territory model

Each configured territory becomes its own Home Assistant device. The bundled catalog
contains the complete administrative hierarchy used by the integration, and setup can
be performed either by direct search or by walking the hierarchy.

Parent-scope alerts apply downward. For example, an oblast-wide alert applies to its
raions and hromadas even if the source does not duplicate a separate row for each child.
Child alerts never make the entire parent active. Instead, oblast and raion entries use
a separate coverage sensor to distinguish full, partial, and mixed situations.

The highest applicable alert level wins (`red` over `yellow`), while threats from all
applicable source rows are merged and de-duplicated.

## Main entities

A city/hromada device normally exposes 11 enabled entities; an oblast/raion also gets
`Alert coverage` for a total of 12.

| Entity | Purpose |
| --- | --- |
| `sensor.ua_<uid>_level` | effective alert level (`clear`, `yellow`, `red`) |
| `sensor.ua_<uid>_coverage` | oblast/raion only: `none`, `full`, `partial`, `mixed` |
| `binary_sensor.ua_<uid>_alert` | simple on/off air-alert state |
| `sensor.ua_<uid>_threats` | localized active threats plus stable raw threat codes |
| `binary_sensor.ua_<uid>_source` | source freshness / availability |
| `sensor.ua_<uid>_last_alert_duration` | last completed alert as `MM:SS`, `H:MM:SS`, or `Dd HH:MM:SS` |
| `sensor.ua_<uid>_last_alert_level` | maximum level reached by that completed alert |
| `sensor.ua_<uid>_last_alert_lag` | source-start → Home Assistant detection lag for the last alert |
| `sensor.ua_<uid>_last_threat_lag` | source-start → Home Assistant detection lag for the last new threat |
| `sensor.ua_<uid>_health` | aggregate data health diagnostic |
| `number.ua_<uid>_poll` | editable global polling interval |
| `number.ua_<uid>_stale` | editable global stale threshold |

Lag values of one second or more are shown as whole seconds. Sub-second values retain
up to two decimal places. Last-alert duration keeps raw numeric seconds in the
`duration_seconds` attribute for automations.

Entity attributes are intentionally kept compact: state duplicates, possible-value
lists, raw internal UID lists, and test markers are not repeated on normal entities.

## Testing automations from the device page

Every UA Alerts territory device shows its configured territory as a separate line in
the **Service** card, directly below **UA Alerts** and above the integration version:

**UA Alerts**<br>
**м. Київ**<br>
**Version 0.1.25**

The prominent **Test alert** administrator action stays short. Opening it brings up a
compact dialog already bound to that territory. You can choose:

- `Off`, `Clear`, `Yellow`, or `Red`;
- any combination of supported threat types.

The test override drives the normal alert/threat entities and events, so existing Home
Assistant automations can be exercised without YAML or entering a territory UID.

Real polling continues in the background. Test states do **not** update persisted
Last Alert history or lag measurements. Resetting the test immediately restores the
latest real source state, and test overrides do not survive a Home Assistant restart.

## Events

UA Alerts fires per-territory events suitable for automations:

- `ua_alert_level_changed`
- `ua_alert_threats_changed`
- `ua_alert_source_availability_changed`

Event payloads retain machine-readable territory, level, threat, and timing context.

## Installation

### HACS custom repository

1. Add `gamba69/home-assistant-ua-alerts` to HACS as a custom repository of type **Integration**.
2. Install **UA Alerts**.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration** and search for **UA Alerts**.
5. Add one or more territories using **Search** or **Tree**.

### Manual installation

Copy `custom_components/ua_alerts/` to `/config/custom_components/ua_alerts/`, restart
Home Assistant, then add **UA Alerts** from **Settings → Devices & services**.

## Territory catalog updates

The integration does not refresh the territory catalog automatically. The bundled
snapshot is immediately usable after installation. Use **Configure → Refresh territory
catalog** only when you explicitly want to download and store a newer catalog. A failed
refresh never replaces the last valid local catalog.

## Diagnostics and reliability

`Data status` remains available even when operational alert entities are unavailable.
Its attributes are limited to useful diagnostics such as sampled source response time,
consecutive errors, HTTP status, last error, and the technical delay reason.

For active air-raid rows, UA Alerts requires the upstream `alert_level` field. Missing
or invalid applicable alert data is treated as invalid data, not silently converted to
`clear`. Unknown future threat codes are preserved instead of being discarded.

## Development and testing

The project includes model/runtime tests and Home Assistant integration tests based on
`pytest-homeassistant-custom-component`, plus Hassfest and HACS validation. Release
contract tests keep the integration version synchronized across `const.py`,
`manifest.json`, the root README, localized READMEs, and localized changelogs.

More detail:

- [English documentation](docs/en/README.md)
- [Русская документация](docs/ru/README.md)
- [Українська документація](docs/uk/README.md)
- [Architecture](ARCHITECTURE.md)
- [Testing and release checks](TESTING.md)
- [Changelog](CHANGELOG.md)

## Project identity

- **Name:** `UA Alerts`
- **Domain:** `ua_alerts`
- **Directory:** `custom_components/ua_alerts/`
- **Repository:** `gamba69/home-assistant-ua-alerts`

## Important

UA Alerts is informational. Do not use it as the only source for safety-critical
decisions. Follow official Ukrainian alert channels and civil-defense guidance.
