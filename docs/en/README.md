# UA Alerts

A Home Assistant custom integration for Ukrainian air-raid alert levels with support for `clear`, `yellow`, and `red` states.

The integration uses the token-free Ubilling proxy for `alerts.in.ua` raw data:

`https://ubilling.net.ua/aerialalerts/?source=aiu&raw`

## Public identity

- Name: **UA Alerts**
- Domain: `ua_alerts`
- Integration directory: `custom_components/ua_alerts/`
- Repository: `gamba69/home-assistant-ua-alerts`
- Current release: **0.1.23**


## Highlights

- one Config Entry per territory;
- multiple territories can be configured at the same time;
- one shared domain-wide polling runtime, regardless of entry count;
- one HTTP request and one response parse per polling cycle;
- domain-wide configurable polling/stale timing (defaults: 3 s / 15 s);
- air-raid level derived only from the source `alert_level` field;
- administrative alert inheritance: oblast -> raion -> hromada, with no false upward propagation;
- threat aggregation/de-duplication plus persistent last-alert state and compact end-to-end lag measurements;
- RU / UK / EN translations;
- no API token required;
- HACS-ready repository layout.

## Installation

### Manual installation

1. Copy `custom_components/ua_alerts` to your Home Assistant configuration directory as:
   `/config/custom_components/ua_alerts`.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration**.
4. Search for **UA Alerts**.
5. Choose how to find the territory: **Search** or **Tree**.
6. Search accepts a territory name, selected common/historical names, or an alerts.in.ua UID and shows the current administrative path for ambiguous results.
7. Tree navigation walks **oblast / standalone city → scope → raion → hromada**.
8. Repeat the setup for every additional territory you want to monitor.

The bundled catalog snapshot contains **1607 territories**: 25 oblast-level territories, 122 raions, 1458 hromadas, and the two cities with special status. A clean installation therefore has the complete selector immediately and does not need network access for catalog setup. For example, `Кагарлицька територіальна громада` is bundled as UID `726` under `Київська область → Обухівський район`; search also recognizes the common/historical `Кагарлик` / `Кагарлыкский район` wording and resolves it to the current territory.

### Administrative inheritance and partial coverage

The raw alerts feed contains alert rows at different administrative scopes. A parent-scope air-raid alert applies to all descendants even when the feed does not repeat a separate row for each child. UA Alerts therefore evaluates a configured hromada against **its own UID + parent raion + parent oblast**, and a configured raion against **its own UID + parent oblast** for whole-territory coverage. The highest applicable `alert_level` wins (`red` over `yellow`), and threats are merged across all applicable rows.

For configured **raions and oblasts**, the integration also aggregates active descendants. This is intentionally not treated as downward inheritance: a hromada alert does not make the whole raion active. Instead it produces **partial coverage** for the parent. The alert-level entity still reports the maximum level present anywhere in the configured territory, while the separate `coverage` sensor says whether that level applies to none, all, part, or a higher-level subpart of the territory.

Coverage codes are:

- `none`: no active air-raid alert anywhere in the configured territory;
- `full`: a direct or inherited alert covers the whole territory, and no child has a higher level;
- `partial`: there is no whole-territory alert, but one or more descendants are active;
- `mixed`: the whole territory has one level and at least one descendant has a higher level (for example, raion-wide yellow plus one hromada red).

For transparency without attribute clutter, the alert-level entity exposes only `alert_scope`, `alert_source_location_title`, and `alert_source_location_type`. `alert_scope=partial` identifies an effective level whose decisive source is a descendant. Detailed source UIDs and active-location lists remain available in integration events and diagnostics instead of being duplicated on every entity state.

The catalog is **never refreshed automatically**. Use **Configure → Refresh territory catalog** on any UA Alerts entry only when you explicitly want to replace the bundled/stored snapshot with a freshly downloaded official alerts.in.ua catalog. A successful manual refresh is stored locally and reused indefinitely; a failed refresh never replaces the last valid catalog.

### HACS custom repository

Once this repository contains the integration files, add it to HACS as a custom repository with category **Integration**, install **UA Alerts**, restart Home Assistant, and add the integration from **Settings → Devices & services**.

## Entities

Eleven entities are enabled by default for a configured hromada or standalone city, including the two editable global timing numbers. Raion and oblast entries get a twelfth operational entity, `alert_coverage`, because those territories can be only partially active. Entity IDs use only the stable alerts.in.ua territory UID and a short technical suffix. The 0.1.23 upgrade migrates previous latency/delay unique IDs to the new lag names; untouched automatic entity IDs are renamed accordingly, while manually renamed entity IDs are preserved.

| Entity | Purpose |
| --- | --- |
| `sensor.ua_<uid>_level` | localized alert level; attributes keep only scope and human-readable source territory context |
| `sensor.ua_<uid>_coverage` | raion/oblast only: coverage state (`none`, `full`, `partial`, `mixed`) plus `full_level_code` / `partial_level_code` |
| `binary_sensor.ua_<uid>_alert` | on for yellow/red, off for clear |
| `sensor.ua_<uid>_threats` | localized threat state; attributes keep active `threat_codes` and detailed `threats` only |
| `binary_sensor.ua_<uid>_source` | source freshness/availability |
| `sensor.ua_<uid>_last_alert_duration` | compact `MM:SS`, `H:MM:SS`, or `Dd HH:MM:SS`; raw seconds stay in `duration_seconds` |
| `sensor.ua_<uid>_last_alert_level` | maximum level reached by the latest fully observed completed alert |
| `sensor.ua_<uid>_last_alert_lag` | end-to-end lag from source `Alert.started_at` to the first snapshot in which HA observes the new alert |
| `sensor.ua_<uid>_last_threat_lag` | end-to-end lag from the latest newly appeared `Threat.started_at` to the first snapshot in which HA observes that threat |
| `sensor.ua_<uid>_health` | aggregate data status: normal / delayed / source error / data error |

`last_alert_lag` is measured only on a valid `clear -> yellow/red` transition and then frozen. `last_threat_lag` similarly measures a newly appearing threat instance. Values of 1 second or more are shown as whole seconds; sub-second values keep up to two decimal places. Both sensors keep their last valid measurements after clear and persist them per territory UID.

`data_health` is the at-a-glance diagnostic entity. It remains available even when operational entities do not. Its attributes are intentionally limited to sampled source response time, consecutive poll errors, HTTP status, last error, and technical delay reason. Alert/threat end-to-end lag is informational and never makes data health `delayed`; that state is reserved for a slow HTTP response.

`last_threat_lag` exposes only the threat code, source start time, and HA detection time. `last_alert_lag` exposes the source start time, HA detection time, and measured level. The duration sensor exposes only `started_at`, `ended_at`, and numeric `duration_seconds`; `last_alert_level` has no custom attributes.

Upgrades from <= 0.1.4 automatically remove the old high-churn diagnostic entities (`received_at`, `data_age`, and the three previous latency variants), so they no longer spam Home Assistant history/activity.

The integration explicitly suggests the short UID-based object IDs above; registry `unique_id` values remain stable after the 0.1.20 migration and continue to contain the location UID.

### Stable machine-readable values

User-facing states are localized where appropriate, while automations can use stable English technical values:

- alert level: the entity state itself is the stable `clear`, `yellow`, or `red` code; custom attributes only explain scope/source territory;
- alert coverage (raion/oblast): the state itself is `none`, `full`, `partial`, or `mixed`; `full_level_code` and `partial_level_code` preserve the whole-territory/child distinction;
- threats: `threat_codes` is the active raw-code list and `threats` keeps the detailed source records; redundant CSV/possible-code copies are no longer attached to every state.

Known threat labels cover the current alerts.in.ua threat enum. A future unknown code is shown simply as an unknown threat; its raw code remains available in the machine-readable attributes and is never discarded.

Russian UI threat labels are intentionally compact: `Тактическая`, `Стратегическая`, `МиГ-31К`, `Баллистика`, `Крылатые`, `Ракеты`, `БПЛА`, `КАБ`, `ПВО`, `Неизвестно`. Raw source codes remain unchanged.

## Events

The integration fires per-territory events:

- `ua_alert_level_changed`
- `ua_alert_threats_changed`
- `ua_alert_source_availability_changed`

Event data contains the location UID, old/new level, threat codes, relevant timestamps, and the latest frozen end-to-end alert/threat latency measurements when available.

## Polling and failure behavior

All configured territories share a single `UAAlertsRuntime`.

A successful cycle performs one request, validates and parses the response once, records one `received_at`, atomically replaces the shared snapshot, then notifies all configured entries.

A failed cycle never means `clear`. The previous valid snapshot remains active. After the configured stale timeout without a successful snapshot, operational entities become unavailable and `source_available` turns off. The first successful snapshot restores them.

Defaults are **polling = 3 s** and **stale = 15 s**. Open **Configure → Polling and stale** on any UA Alerts entry to change them. These are shared domain-wide settings: changing them on one territory changes the singleton runtime for every configured territory. Polling is limited to 3–60 seconds; stale is limited to 6–600 seconds and must be at least twice the polling interval.

The 3-second minimum is intentional because the Ubilling source caches the raw data for about 3 seconds; polling faster would not provide fresher information.

## Source-schema safety

For an active `air_raid` record, UA Alerts intentionally requires the source `alert_level` field and accepts only `yellow` or `red`. It does **not** infer the level from text, timestamps, or other alert fields.

If an applicable active record (the configured territory, one of its administrative parents, or an aggregated descendant for a raion/oblast entry) is delivered in a legacy format without `alert_level`, that configured territory is marked as having invalid data; the condition is never silently converted to `clear`. Other unrelated configured territories continue to work.

Unknown `threat_type` values are preserved rather than rejected, so new upstream threat codes can appear without an integration update.

## Diagnostics

Download diagnostics from the integration entry in Home Assistant to inspect:

- runtime status and registered-entry count;
- last request and last successful fetch;
- source cache timestamp;
- HTTP status and response time;
- consecutive errors and recent error summaries;
- computed state, threats, availability, source timestamps, and the last end-to-end alert/threat latency measurements for the selected territory.

The full raw source snapshot is deliberately excluded from diagnostics.

## Testing

The repository contains two layers of tests:

1. HA-independent model/runtime tests covering validation, level precedence, threat handling, timestamps, stale/recovery, concurrency and lifecycle behavior.
2. Home Assistant integration tests using `pytest-homeassistant-custom-component`, targeting Home Assistant 2026.9.x / Python 3.14.

CI also includes Hassfest and HACS validation.

## Important

This integration is informational. Do not use it as the only source for safety-critical decisions. Follow official Ukrainian alert channels and civil-defense guidance.

## Project documentation

- [Architecture](ARCHITECTURE.md)
- [Testing and release checks](TESTING.md)
- [Changelog](CHANGELOG.md)
