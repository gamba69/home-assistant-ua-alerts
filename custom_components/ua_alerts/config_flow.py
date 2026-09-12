"""Config and options flows for UA Alerts."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .catalog import CatalogRefreshError, async_load_catalog, async_refresh_catalog, catalog_is_full
from .catalog_search import location_path_label, search_catalog
from .display import THREAT_CODE_ORDER, level_label, normalize_language, threat_label
from .const import (
    ALERT_LEVEL_CLEAR,
    ALERT_LEVEL_RED,
    ALERT_LEVEL_YELLOW,
    CONF_LOCATION_TITLE,
    CONF_LOCATION_TYPE,
    CONF_LOCATION_UID,
    DOMAIN,
    MAX_POLL_INTERVAL_SECONDS,
    MAX_STALE_AFTER_SECONDS,
    MIN_POLL_INTERVAL_SECONDS,
    MIN_STALE_AFTER_SECONDS,
    OPT_POLL_INTERVAL,
    OPT_STALE_AFTER,
)
from .models import LocationDefinition
from .settings import async_apply_settings, async_get_settings, validate_settings

_SCOPE = "scope"
_SCOPE_OBLAST = "oblast"
_SCOPE_RAION = "raion"
_SCOPE_HROMADA = "hromada"
_CONF_REGION_UID = "region_uid"
_CONF_RAION_UID = "raion_uid"
_CONF_QUERY = "query"
_CONF_SEARCH_UID = "search_uid"
_CONF_TEST_LEVEL = "test_level"
_CONF_TEST_THREATS = "test_threats"
_TEST_LEVEL_OFF = "off"
_TEST_OFF_LABELS = {"en": "Off", "ru": "Выключено", "uk": "Вимкнено"}


class UAAlertsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle UA Alerts configuration."""

    VERSION = 1

    def __init__(self) -> None:
        self._catalog: tuple[LocationDefinition, ...] = ()
        self._region: LocationDefinition | None = None
        self._district: LocationDefinition | None = None
        self._scope: str | None = None
        self._search_results: dict[str, LocationDefinition] = {}
        self._search_result_labels: dict[str, str] = {}

    async def _async_catalog(self) -> tuple[LocationDefinition, ...]:
        if not self._catalog:
            self._catalog = await async_load_catalog(self.hass)
        return self._catalog

    def _location_map(self) -> dict[str, LocationDefinition]:
        return {location.location_uid: location for location in self._catalog}

    async def _async_create_location(self, location: LocationDefinition) -> ConfigFlowResult:
        await self.async_set_unique_id(f"location_{location.location_uid}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=location.location_title,
            data={
                CONF_LOCATION_UID: location.location_uid,
                CONF_LOCATION_TITLE: location.location_title,
                CONF_LOCATION_TYPE: location.location_type,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose between direct search and hierarchical navigation."""
        catalog = await self._async_catalog()
        if not catalog_is_full(catalog):
            return await self.async_step_catalog_setup()
        return self.async_show_menu(
            step_id="user",
            menu_options=["search", "tree"],
            description_placeholders={"catalog_count": str(len(catalog))},
        )

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search the full catalog by a place, district, alias, or UID."""
        await self._async_catalog()
        errors: dict[str, str] = {}
        if user_input is not None:
            query = str(user_input.get(_CONF_QUERY, "")).strip()
            results = search_catalog(self._catalog, query)
            if results:
                self._search_results = {
                    result.location.location_uid: result.location for result in results
                }
                self._search_result_labels = {
                    result.location.location_uid: result.label for result in results
                }
                return await self.async_step_search_results()
            errors["base"] = "location_not_found"

        return self.async_show_form(
            step_id="search",
            data_schema=vol.Schema({vol.Required(_CONF_QUERY): str}),
            errors=errors,
            description_placeholders={"catalog_count": str(len(self._catalog))},
        )

    async def async_step_search_results(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose one unambiguous result from the direct search."""
        results = getattr(self, "_search_results", {})
        labels = getattr(self, "_search_result_labels", {})
        if not results:
            return await self.async_step_search()

        errors: dict[str, str] = {}
        if user_input is not None:
            location = results.get(str(user_input.get(_CONF_SEARCH_UID, "")))
            if location is not None:
                return await self._async_create_location(location)
            errors["base"] = "invalid_location"

        return self.async_show_form(
            step_id="search_results",
            data_schema=vol.Schema(
                {
                    vol.Required(_CONF_SEARCH_UID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=uid, label=labels.get(uid, location_path_label(item)))
                                for uid, item in results.items()
                            ],
                            multiple=False,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            errors=errors,
            description_placeholders={"result_count": str(len(results))},
        )

    async def async_step_tree(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Navigate the territory hierarchy from oblast to hromada."""
        catalog = await self._async_catalog()
        locations = self._location_map()
        if user_input is not None:
            region = locations.get(str(user_input.get(_CONF_REGION_UID, "")))
            if region is not None and region.location_type in {"oblast", "city"}:
                self._region = region
                if region.location_type == "city":
                    return await self._async_create_location(region)
                has_raions = any(
                    item.location_type == "raion" and item.oblast_uid == region.location_uid
                    for item in catalog
                )
                if not has_raions:
                    return await self._async_create_location(region)
                return await self.async_step_scope()

        top_level = sorted(
            (item for item in catalog if item.location_type in {"oblast", "city"}),
            key=lambda item: (
                0 if item.location_type == "city" else 1,
                item.location_title.casefold(),
            ),
        )
        return self.async_show_form(
            step_id="tree",
            data_schema=vol.Schema(
                {
                    vol.Required(_CONF_REGION_UID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=item.location_uid, label=item.location_title)
                                for item in top_level
                            ],
                            multiple=False,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            description_placeholders={"catalog_count": str(len(catalog))},
        )

    async def async_step_scope(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose oblast, raion, or hromada level."""
        if self._region is None:
            return self.async_abort(reason="invalid_location")

        if user_input is not None:
            scope = str(user_input.get(_SCOPE, ""))
            if scope == _SCOPE_OBLAST:
                return await self._async_create_location(self._region)
            if scope in {_SCOPE_RAION, _SCOPE_HROMADA}:
                self._scope = scope
                return await self.async_step_raion()

        schema = vol.Schema(
            {
                vol.Required(_SCOPE): SelectSelector(
                    SelectSelectorConfig(
                        options=[_SCOPE_OBLAST, _SCOPE_RAION, _SCOPE_HROMADA],
                        multiple=False,
                        mode=SelectSelectorMode.LIST,
                        translation_key="territory_scope",
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="scope",
            data_schema=schema,
            description_placeholders={"region": self._region.location_title},
        )

    async def async_step_raion(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose a raion within the selected oblast."""
        if self._region is None or self._scope not in {_SCOPE_RAION, _SCOPE_HROMADA}:
            return self.async_abort(reason="invalid_location")

        raions = sorted(
            (
                item
                for item in self._catalog
                if item.location_type == "raion" and item.oblast_uid == self._region.location_uid
            ),
            key=lambda item: item.location_title.casefold(),
        )
        by_uid = {item.location_uid: item for item in raions}

        if user_input is not None:
            district = by_uid.get(str(user_input.get(_CONF_RAION_UID, "")))
            if district is not None:
                self._district = district
                if self._scope == _SCOPE_RAION:
                    return await self._async_create_location(district)
                return await self.async_step_hromada()

        schema = vol.Schema(
            {
                vol.Required(_CONF_RAION_UID): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=item.location_uid, label=item.location_title)
                            for item in raions
                        ],
                        multiple=False,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="raion",
            data_schema=schema,
            description_placeholders={"region": self._region.location_title},
        )

    async def async_step_hromada(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose a hromada within the selected raion."""
        if self._district is None:
            return self.async_abort(reason="invalid_location")

        hromadas = sorted(
            (
                item
                for item in self._catalog
                if item.location_type == "hromada" and item.raion_uid == self._district.location_uid
            ),
            key=lambda item: item.location_title.casefold(),
        )
        by_uid = {item.location_uid: item for item in hromadas}

        if user_input is not None:
            location = by_uid.get(str(user_input.get(CONF_LOCATION_UID, "")))
            if location is not None:
                return await self._async_create_location(location)

        schema = vol.Schema(
            {
                vol.Required(CONF_LOCATION_UID): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=item.location_uid, label=item.location_title)
                            for item in hromadas
                        ],
                        multiple=False,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="hromada",
            data_schema=schema,
            description_placeholders={"raion": self._district.location_title},
        )

    async def async_step_catalog_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer an explicit first-run catalog refresh when only fallback data exists."""
        return self.async_show_menu(
            step_id="catalog_setup",
            menu_options=["refresh_catalog_setup", "fallback"],
            description_placeholders={"catalog_count": str(len(self._catalog))},
        )

    async def async_step_refresh_catalog_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Refresh the full catalog after an explicit setup action."""
        try:
            self._catalog = await async_refresh_catalog(self.hass)
        except CatalogRefreshError:
            return self.async_show_form(
                step_id="catalog_refresh_failed",
                data_schema=vol.Schema({}),
                errors={"base": "catalog_refresh_failed"},
            )
        return await self.async_step_user()

    async def async_step_catalog_refresh_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retry the explicit first-run catalog refresh."""
        if user_input is not None:
            return await self.async_step_refresh_catalog_setup(user_input)
        return self.async_show_form(
            step_id="catalog_refresh_failed",
            data_schema=vol.Schema({}),
            errors={"base": "catalog_refresh_failed"},
        )

    async def async_step_fallback(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Use the bundled fallback catalog without any network request."""
        locations = self._location_map()
        errors: dict[str, str] = {}
        if user_input is not None:
            location = locations.get(str(user_input.get(CONF_LOCATION_UID, "")))
            if location is None:
                errors[CONF_LOCATION_UID] = "invalid_location"
            else:
                return await self._async_create_location(location)

        type_order = {"city": 0, "oblast": 1, "raion": 2, "hromada": 3, "unknown": 4}
        options = [
            SelectOptionDict(
                value=item.location_uid,
                label=f"{item.location_title} · UID {item.location_uid}",
            )
            for item in sorted(
                locations.values(),
                key=lambda item: (type_order.get(item.location_type, 9), item.location_title.casefold()),
            )
        ]
        return self.async_show_form(
            step_id="fallback",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATION_UID): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "UAAlertsOptionsFlow":
        """Create the global timing options flow."""
        return UAAlertsOptionsFlow()


class UAAlertsOptionsFlow(OptionsFlow):
    """Edit domain-wide settings and explicitly refresh the location catalog."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show settings actions. Catalog network access is manual only."""
        current = await async_get_settings(self.hass)
        catalog = await async_load_catalog(self.hass)
        return self.async_show_menu(
            step_id="init",
            menu_options=["testing", "timing", "refresh_catalog"],
            description_placeholders={
                "polling": f"{current.poll_interval:g}",
                "stale": f"{current.stale_after:g}",
                "catalog_count": str(len(catalog)),
            },
        )

    async def async_step_testing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Temporarily override one territory for automation testing."""
        coordinator = self.config_entry.runtime_data
        language = normalize_language(self.hass.config.language)
        current_level = coordinator.test_override_level or _TEST_LEVEL_OFF
        current_threats = list(coordinator.test_override_threat_codes)
        errors: dict[str, str] = {}

        if user_input is not None:
            level = str(user_input.get(_CONF_TEST_LEVEL, _TEST_LEVEL_OFF))
            threats = tuple(
                str(code) for code in user_input.get(_CONF_TEST_THREATS, ())
            )
            try:
                if level == _TEST_LEVEL_OFF:
                    coordinator.clear_test_override()
                else:
                    coordinator.set_test_override(level, threats)
            except ValueError:
                errors["base"] = "invalid_test"
            else:
                return self.async_abort(
                    reason="test_updated",
                    description_placeholders={"location": coordinator.location_title},
                )

        level_options = [
            SelectOptionDict(
                value=_TEST_LEVEL_OFF,
                label=_TEST_OFF_LABELS[language],
            ),
            *[
                SelectOptionDict(value=code, label=level_label(code, language))
                for code in (
                    ALERT_LEVEL_CLEAR,
                    ALERT_LEVEL_YELLOW,
                    ALERT_LEVEL_RED,
                )
            ],
        ]
        threat_options = [
            SelectOptionDict(value=code, label=threat_label(code, language))
            for code in THREAT_CODE_ORDER
        ]
        return self.async_show_form(
            step_id="testing",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        _CONF_TEST_LEVEL,
                        default=current_level,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=level_options,
                            multiple=False,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        _CONF_TEST_THREATS,
                        default=current_threats,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=threat_options,
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"location": coordinator.location_title},
        )

    async def async_step_timing(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edit the global polling and stale thresholds."""
        errors: dict[str, str] = {}
        current = await async_get_settings(self.hass)

        if user_input is not None:
            try:
                settings = validate_settings(
                    user_input.get(OPT_POLL_INTERVAL),
                    user_input.get(OPT_STALE_AFTER),
                )
            except ValueError as err:
                errors["base"] = (
                    "stale_too_short" if "twice" in str(err) else "invalid_timing"
                )
            else:
                await async_apply_settings(
                    self.hass,
                    settings,
                    skip_entry_id=self.config_entry.entry_id,
                )
                return self.async_create_entry(data=settings.as_options())

        schema = vol.Schema(
            {
                vol.Required(
                    OPT_POLL_INTERVAL,
                    default=current.poll_interval,
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_POLL_INTERVAL_SECONDS,
                        max=MAX_POLL_INTERVAL_SECONDS,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                vol.Required(
                    OPT_STALE_AFTER,
                    default=current.stale_after,
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_STALE_AFTER_SECONDS,
                        max=MAX_STALE_AFTER_SECONDS,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="timing",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_refresh_catalog(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Refresh the territory catalog only after this explicit user action."""
        try:
            catalog = await async_refresh_catalog(self.hass)
        except CatalogRefreshError:
            return self.async_show_form(
                step_id="refresh_catalog_failed",
                data_schema=vol.Schema({}),
                errors={"base": "catalog_refresh_failed"},
            )
        return self.async_abort(
            reason="catalog_refreshed",
            description_placeholders={"catalog_count": str(len(catalog))},
        )

    async def async_step_refresh_catalog_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow retry after a manual catalog refresh failure."""
        if user_input is not None:
            return await self.async_step_refresh_catalog(user_input)
        return self.async_show_form(
            step_id="refresh_catalog_failed",
            data_schema=vol.Schema({}),
            errors={"base": "catalog_refresh_failed"},
        )
