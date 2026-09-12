# Changelog

## 0.1.23
- Added the configured territory directly to the device service-card configuration row, so the entry is immediately identifiable (for example `UA Alerts · м. Київ`).
- Renamed `Last alert delay` / `Last threat delay` to `Last alert lag` / `Last threat lag`, including entity keys/IDs and event aliases, with safe registry migration from both older latency names and 0.1.20–0.1.22 delay names.
- Lag values now use whole seconds at 1 s and above, and up to two decimal places only below 1 s. Last-alert duration now uses compact `MM:SS`, `H:MM:SS`, or localized-day `Dd HH:MM:SS` formatting while retaining raw `duration_seconds`.
- Removed redundant entity attributes that duplicated state, possible-value lists, source UIDs, and test markers; retained only useful context and machine-readable details.

## 0.1.22
- Added a prominent **Test alert** action directly to every UA Alerts territory device page for administrators.
- The action opens a compact territory-scoped dialog with alert level and multi-threat selection; the territory is taken from the device automatically.
- The normal integration configuration link remains available in the device overflow menu. Existing test semantics are unchanged: real polling and Last Alert / delay history stay independent from the test override.

## 0.1.21
- Added editable `Poll interval` and `Stale after` configuration-number entities to every territory device. The values remain domain-wide and changes from any territory are propagated live to all entries.
- Added territory-scoped alert testing in Configure: choose `Off` / `Clear` / `Yellow` / `Red` and any combination of supported threats. The override drives the normal alert/threat entities and events while real polling and Last Alert / delay history continue independently.
- Territory devices now link back to their exact UA Alerts Config Entry in Home Assistant, so testing opens for that territory without selecting it again.

## 0.1.20
- Replaced the diagnostic `Alert latency` / `Threat latency` entities with ordinary state sensors `Last alert delay` and `Last threat delay`, preserving the measurements across upgrade through entity-registry migration.
- Added `Last alert duration` and `Last alert level` (maximum yellow/red level) for the latest fully observed completed alert.
- Added persistent alert lifecycle state so a normally observed alert survives a Home Assistant restart and is finalized correctly after `clear`; stale/source/data errors never close an alert.
- Startup in the middle of an untracked active alert deliberately does not fabricate last-alert duration or maximum level.

## 0.1.19
- Fixed HA 2026.9 device-registry tests after removal of `DeviceEntry.translation_key`.
- Synchronized release metadata and public documentation, and added a concise landing-page README description.

## 0.1.18
- Updated HA regression tests for current 2026.9 APIs and made version checks derive from `const.py`.
- Synchronized the Python `VERSION` constant with the manifest.

## 0.1.17
- Fixed Hassfest manifest ordering and declared the config-entry-only schema.
- Moved Project tests to Python 3.14 and configured pip caching for `requirements_test.txt`.

## 0.1.16

- Made config-flow catalog wording neutral so a manually refreshed stored catalog is not incorrectly described as the bundled snapshot.
- Prepared the project for its first public GitHub/HACS release without changing runtime alert semantics.
- Added MIT license and tri-language repository documentation in `docs/en`, `docs/ru`, and `docs/uk`, with short multilingual root navigation files matching the Vacuum Schedule repository pattern.
- Split CI into `hacs.yaml`, `hassfest.yaml`, and `tests.yaml`; aligned actions versions and Python 3.13 with the companion repository, added JSON/YAML validation and generated-patch rejection.
- Added `render_readme: true` to HACS metadata and strengthened repository-contract regression tests.
- Added public architecture and release-testing documentation, including explicit warning that a local HA-module skip is not a full Home Assistant E2E pass.

## 0.1.15

- Added `possible_threat_codes` to the Threats sensor attributes so Home Assistant always exposes the complete supported set of threat codes, even when no threats are currently active.
- The list contains the ten current source codes in stable display order and is separate from `threat_codes`, which continues to contain only currently active threats.

## 0.1.14

- Fixed short entity-ID migration after removing and re-adding a territory. Home Assistant restores the previous `entity_id` from its deleted-entity registry before applying the integration's current `suggested_object_id`; UA Alerts now runs the safe migration again after platform setup.
- Recognizes the exact pre-0.1.8 automatic `<location>_<entity_key>` naming pattern (for example `sensor.m_kiiv_threat_codes`) and migrates it to the UID-based ID (`sensor.ua_31_threats`).
- Arbitrary manually renamed entity IDs remain preserved; the legacy-pattern exception is deliberately narrow.
- Added Home Assistant regression coverage for restored deleted `threat_codes` IDs and preserved custom deleted IDs, plus pure tests for the legacy-ID helper.

## 0.1.13

- Shortened Russian threat labels for compact Home Assistant cards and notifications: `Тактическая`, `Стратегическая`, `МиГ-31К`, `Баллистика`, `Крылатые`, `Ракеты`, `БПЛА`, `КАБ`, `ПВО`, `Неизвестно`.
- Regenerated all Russian multi-threat frontend enum combinations from the same compact vocabulary, so combinations remain consistent and no old long labels leak through.
- Raw `threat_type` codes and machine-readable attributes are unchanged.

## 0.1.12

- Added partial-alert aggregation for configured raions and oblasts. Child hromada/raion alerts now affect the selected parent territory without being misrepresented as a full-territory alert.
- Added `sensor.ua_<uid>_coverage` ("Alert coverage" / "Охват тревоги" / "Охоплення тривоги") for raion and oblast entries only. Its stable codes are `none`, `full`, `partial`, and `mixed`.
- Coverage semantics: `partial` means only descendants are active; `full` means the whole selected territory is covered by a direct/inherited alert; `mixed` means a full-territory level exists and a descendant has a higher level.
- Alert level for raion/oblast is now the maximum level anywhere in the selected territory (`red` over `yellow`), while `full_level_code` and `partial_level_code` preserve the distinction between whole-territory and child-only levels.
- Threats from active descendants are aggregated for parent territories, and partial alerts participate in alert/threat latency tracking without being promoted to full coverage.
- Added `possible_level_codes = [clear, yellow, red]` to the alert-level entity.
- Coverage attributes expose `coverage_code`, `possible_coverage_codes`, `full_level_code`, `partial_level_code`, `possible_level_codes`, and the active full/partial source UID lists.
- Added pure regression tests for partial raion/oblast alerts, mixed coverage, full-red precedence, inherited oblast + child overrides, descendant lookup, and child threat aggregation.

## 0.1.11

- Fixed a critical hierarchy bug for hromadas and raions: an active air-raid alert on a parent administrative territory now applies to its descendants.
- A hromada now evaluates its own UID plus its parent raion and oblast; a raion evaluates its own UID plus its parent oblast. Parent alerts propagate downward only; a child hromada alert does not incorrectly mark the whole raion active.
- The effective alert level is the highest applicable source level (`red` over `yellow`). Threats from all applicable direct/inherited alert rows are merged and de-duplicated.
- Alert latency for a newly inherited alert uses the actual `Alert.started_at` of the parent alert row that made the configured territory active. Threat latency likewise observes threats inherited from applicable parent rows.
- Added alert-level source attributes: `alert_scope` (`direct` / `inherited`), source UID/title/type, and `active_alert_location_uids`, so Home Assistant shows why a descendant territory is active.
- Added the same hierarchy/source context to integration events and downloaded diagnostics.
- Added regression tests for Obukhiv raion -> Kaharlyk hromada inheritance, direct red overriding inherited yellow, oblast inheritance, threat merging, invalid ancestor data, latency, and prevention of upward propagation.

## 0.1.10

- Persist the latest alert and threat latency measurements per territory UID using Home Assistant storage.
- Restore both latency sensor values and their source/detection metadata after a Home Assistant restart.
- Restored measurements do not create a fake transition: startup during an already-active alert/threat still establishes only the live baseline, and the next genuine new event replaces the stored measurement.
- Removed alert/threat end-to-end latency from the aggregate `data_health` verdict. A value such as 28 seconds remains a measurement and is no longer labeled anomalous merely because it exceeds a fixed threshold.
- `delayed` health is now reserved for a slow HTTP response from the configured source; source/data failures keep their existing higher-priority states.
- Latency storage writes occur only when a new meaningful measurement is produced, not on every 3-second polling cycle.

## 0.1.9

- Added one aggregate diagnostic sensor, `sensor.ua_<uid>_health` ("Data status" / "Состояние данных" / "Стан даних").
- Added four frontend-localized enum states with stable technical values: `normal`, `delayed`, `source_error`, and `data_error`.
- The health entity deliberately remains available when the alert source or territory data is broken, so it can explain failures instead of becoming unavailable itself.
- `source_error` covers polling failures or stale/unavailable source data; `data_error` covers a valid source snapshot that cannot produce valid data for the configured territory.
- `delayed` detects a slow source response (>= 1.5 s) and unusually slow recent end-to-end alert/threat delivery (> max(6 s, 2 x poll interval), for five minutes after observation).
- Health attributes expose the last alert/threat latency, sampled source response time, consecutive errors, HTTP status, last error, and technical delay reason.
- Volatile health details are throttled to a 30-second sample interval unless something meaningful changes, avoiding a return of 3-second diagnostic/history churn.
- Added pure health-policy tests and expanded Home Assistant contract coverage.

## 0.1.8

- Replaced long territory-name-based Home Assistant entity IDs with short UID-based IDs: `ua_<uid>_<suffix>`.
- New IDs are `sensor.ua_<uid>_level`, `sensor.ua_<uid>_threats`, `sensor.ua_<uid>_alert_latency`, `sensor.ua_<uid>_threat_latency`, `binary_sensor.ua_<uid>_alert`, and `binary_sensor.ua_<uid>_source`.
- Kept existing integration `unique_id` values unchanged so entity registry identity and continuity are preserved.
- Added a one-time safe migration for existing automatically generated IDs; manually renamed entity IDs are detected and left untouched.
- Entity IDs no longer depend on territory spelling, transliteration, localization, or later administrative renames.

## 0.1.7

- Bundled the complete territory catalog directly in the integration package: 1607 entries (25 oblast-level territories, 122 raions, 1458 hromadas, and 2 special-status cities).
- Added two independent territory-selection paths: direct **Search** and hierarchical **Tree** navigation.
- Search accepts names and alerts.in.ua UID values and shows oblast/raion context for ambiguous hromada names.
- Added curated current/historical aliases, including `Кагарлик` / `Кагарлыкский район` → current `Кагарлицька територіальна громада` (UID 726, Kyiv oblast / Obukhiv raion).
- Updated bundled names for known administrative renames such as Volodymyrskyi, Samarivskyi, Zviahelskyi, Siverskodonetskyi, Sheptytskyi and Berestynskyi raions.
- Kept catalog updates strictly user-initiated through **Configure → Refresh territory catalog**; there is no TTL or automatic catalog network traffic.
- Added catalog completeness, hierarchy, alias-search, disambiguation, and config-flow regression tests.

## 0.1.6

- Added `threat_latency`: end-to-end delay from a threat's source `Threat.started_at` to the first Home Assistant snapshot that contains that newly appeared threat.
- The threat latency is frozen at detection time and never grows with threat/alert age.
- The sensor always keeps the latest successfully measured threat latency; a later threat during an already active alert replaces the previous measurement.
- Existing threats at Home Assistant startup establish a baseline and do not produce fake multi-minute latency values.
- Level-only changes of the same threat instance do not create a new latency measurement.
- If multiple new threats arrive in the same polling snapshot, the threat with the latest `started_at` is exposed as the latest measurement.
- Added technical attributes: `threat_code`, `threat_level_code`, `threat_started_at`, `threat_detected_at`, and `threat_source_message`.
- Added threat-latency details to integration events and diagnostics.
- Expanded regression coverage for startup, repeated polling, level-only changes, multiple simultaneous threat additions, clear/reset, and clock anomalies.

## 0.1.5

- Reworked latency semantics to one end-to-end measurement: source `Alert.started_at` -> first Home Assistant snapshot that observes the new alert.
- Latency is measured only on a valid `clear -> yellow/red` transition and is frozen for the lifetime of that alert; it no longer grows with alert age.
- Startup during an already-active alert is not misreported as latency.
- Removed `data_age`, `event_time`, `source_updated`, `received_at`, `source_processing_latency`, `delivery_latency`, and `observed_latency` entities.
- Added one `alert_latency` diagnostic sensor with stable technical attributes: alert start time, HA detection time, and detected level code.
- Obsolete <= 0.1.4 diagnostic entity-registry entries are removed automatically on upgrade, eliminating `received_at` activity/history spam.
- Parser now uses the source alert-level `started_at` field separately from individual threat `started_at`.

## 0.1.4

- Device name is now the exact catalog territory title (for example `м. Київ`); backend-language prefixes such as `City:` are no longer used.
- Explicitly migrates/clears legacy device translation metadata from <= 0.1.3.
- Territory devices are registered as Home Assistant service devices.
- Device info now exposes the integration version and source configuration URL using standard Home Assistant fields.
- Fixed the internal VERSION constant to stay in sync with the manifest.

## 0.1.3

- Fixed territory type localization in the Home Assistant device list.
- Removed location type from `DeviceInfo.model`; old `City`/`Oblast` values are explicitly cleared on reload.
- Added frontend-localized device names for oblast, raion, city, hromada, and unknown territory types.
- Added frontend-localized threat states, including multi-threat combinations; raw English codes remain in attributes.

## 0.1.2

- localized user-facing threat states for the complete current alerts.in.ua threat enum;
- stable English machine codes moved/exposed as entity attributes (`level_code`, `threat_codes`, `threat_codes_csv`);
- localized device territory type instead of raw values such as `city`;
- removed every automatic catalog refresh and TTL;
- added explicit manual catalog refresh in Configure and first-run setup when only fallback data exists;
- preserved the last valid full catalog on refresh failure.

## 0.1.1

- redesigned local HACS brand icon;
- full official location catalog refresh with 24-hour local cache;
- hierarchical location setup: oblast/city → level → raion → hromada;
- domain-wide configurable polling and stale timings;
- live timing changes without recreating the singleton runtime;
- expanded parser/timing/runtime tests.

## 0.1.0

Initial release candidate.

- token-free Ubilling / alerts.in.ua raw-data source;
- shared singleton polling runtime for all config entries;
- fixed 3 s polling and 15 s stale threshold;
- independent per-location coordinators;
- `clear` / `yellow` / `red` air-raid levels;
- threat aggregation and de-duplication;
- source/event/receive timestamps and latency diagnostics;
- four default user entities and seven disabled-by-default diagnostic entities;
- per-location Home Assistant events;
- config flow with duplicate-UID protection;
- EN / RU / UK translations;
- HACS-ready repository structure;
- extensive model, runtime, lifecycle and Home Assistant tests.
