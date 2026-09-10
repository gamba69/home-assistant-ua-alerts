# Architecture

## Overview

UA Alerts is a Home Assistant custom integration built around a **domain-scoped singleton polling runtime** and lightweight **per-territory coordinators**. Multiple configured territories never create parallel polling loops: one raw snapshot is fetched and parsed once, then reused by every entry.

## Main components

- `runtime.py` owns the single HTTP polling loop, request serialization, source freshness and the latest shared parsed snapshot.
- `models.py` validates/parses source payloads and contains the pure alert, threat, hierarchy and latency logic.
- `coordinator.py` evaluates one configured territory against the shared snapshot, tracks alert/threat transitions and emits Home Assistant updates/events.
- `sensor.py` and `binary_sensor.py` expose operational and diagnostic entities.
- `catalog.py`, `catalog_parser.py` and `catalog_search.py` provide the bundled administrative catalog, manual refresh and search/tree selection support.
- `config_flow.py` handles territory creation and domain-wide polling/stale options.
- `latency_storage.py` persists the latest valid alert/threat latency measurement per territory UID.
- `health.py` computes the compact data-health state without treating upstream publication latency as an integration fault.
- `entity_ids.py` defines stable UID-based entity IDs and safe migration from old automatic names.

## Runtime lifecycle

The first configured entry creates the `UAAlertsRuntime`; subsequent entries register callbacks on the same instance. The last unloaded entry stops it. Lifecycle and HTTP operations are protected by separate asyncio locks, preventing duplicate polling tasks and overlapping fetches.

Each successful poll:

1. performs one HTTP GET;
2. validates the payload;
3. records one `received_at` timestamp;
4. parses the raw feed once;
5. atomically replaces the shared snapshot;
6. notifies all registered territory coordinators.

A failed poll does not synthesize `clear`. The last successful snapshot remains available until the configured stale threshold is exceeded.

## Administrative hierarchy

Territories are represented by stable `alerts.in.ua` UIDs and parent relations from the bundled catalog.

Downward inheritance is authoritative: an oblast alert applies to its raions and hromadas; a raion alert applies to its hromadas. For a selected hromada, the evaluator considers its own UID plus parent raion and oblast. For a selected raion, it considers its own UID plus parent oblast for whole-territory coverage.

Upward aggregation is deliberately different. A child alert does not turn the entire parent territory into a full alert. For raions and oblasts, child activity contributes **partial coverage**. Coverage states are `none`, `full`, `partial`, and `mixed`; the alert-level sensor still reports the highest level present anywhere in the selected territory.

## Level and threat model

Only active `air_raid` records are relevant. `alert_level` must be `yellow` or `red`; the integration does not infer a level from text or timestamps. Among applicable records, `red` has priority over `yellow`.

Threats from every applicable full or partial source row are merged and de-duplicated. Known threat codes are translated for display, while raw machine codes remain available in attributes. Unknown future codes are preserved instead of being discarded.

## Latency semantics

Alert latency is measured only after a valid baseline and on a genuine `clear -> active` transition:

`Alert.started_at -> first shared snapshot received_at in which Home Assistant observes the alert`

Threat latency is measured for a newly observed threat instance identified by `(threat_type, started_at)`:

`Threat.started_at -> first shared snapshot received_at containing that threat`

Measurements are frozen, persisted by territory UID, and restored after restart. Startup during an already-active alert/threat establishes a baseline instead of creating a false large latency.

## Entity identity

Entity IDs use the stable territory UID, for example `sensor.ua_31_level`. Home Assistant `unique_id` values remain stable across releases. A migration shortens untouched legacy automatic IDs while preserving manually renamed entity IDs; the migration also runs after platform setup to catch IDs restored from Home Assistant's deleted-entity registry.

## Catalog policy

The integration ships a complete catalog snapshot and never refreshes it automatically. A user can explicitly refresh the catalog from the options flow. A failed refresh never replaces the last valid stored catalog.

## Failure and diagnostics model

Operational entities become unavailable only when the source is stale or territory data is invalid. The `data_health` sensor remains available to explain `normal`, `delayed`, `source_error`, or `data_error` states. `delayed` is reserved for slow HTTP source response; alert/threat end-to-end latency is informational and never by itself marks health as degraded.
