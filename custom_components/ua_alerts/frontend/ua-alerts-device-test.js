const DOMAIN = "ua_alerts";
const MANUFACTURER = "UA Alerts";
const PATCH_MARK = Symbol.for("ua-alerts.device-test-action.v1");

const TEXT = {
  en: {
    action: "Test alert",
    title: "Test alert",
    level: "Alert level",
    threats: "Threats",
    threatsHint: "Select any number of threats",
    apply: "Apply",
    reset: "Reset test",
    cancel: "Cancel",
    loading: "Loading…",
    loadError: "Could not load test controls.",
    saveError: "Could not apply test state.",
    active: "Test override is active",
  },
  ru: {
    action: "Тестирование тревоги",
    title: "Тестирование тревоги",
    level: "Уровень тревоги",
    threats: "Угрозы",
    threatsHint: "Можно выбрать несколько угроз",
    apply: "Применить",
    reset: "Сбросить тест",
    cancel: "Отмена",
    loading: "Загрузка…",
    loadError: "Не удалось загрузить тестирование.",
    saveError: "Не удалось применить тестовое состояние.",
    active: "Тестовая подмена активна",
  },
  uk: {
    action: "Тестування тривоги",
    title: "Тестування тривоги",
    level: "Рівень тривоги",
    threats: "Загрози",
    threatsHint: "Можна вибрати кілька загроз",
    apply: "Застосувати",
    reset: "Скинути тест",
    cancel: "Скасувати",
    loading: "Завантаження…",
    loadError: "Не вдалося завантажити тестування.",
    saveError: "Не вдалося застосувати тестовий стан.",
    active: "Тестова підміна активна",
  },
};

function languageOf(hass) {
  const raw = hass?.language || hass?.locale?.language || "en";
  const lang = String(raw).replace("_", "-").split("-", 1)[0].toLowerCase();
  return TEXT[lang] ? lang : "en";
}

function stringsFor(hass) {
  return TEXT[languageOf(hass)];
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

class UAAlertsTestDialog extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._state = null;
    this._error = null;
    this._busy = false;
    this._onKeyDown = (event) => {
      if (event.key === "Escape") this.close();
    };
  }

  connectedCallback() {
    window.addEventListener("keydown", this._onKeyDown);
    this._render();
    this._load();
  }

  disconnectedCallback() {
    window.removeEventListener("keydown", this._onKeyDown);
  }

  async _load() {
    try {
      this._state = await this.hass.callWS({
        type: "ua_alerts/test/get",
        entry_id: this.entryId,
        language: this.hass.language || this.hass.locale?.language || "en",
      });
      this._error = null;
    } catch (error) {
      console.error("UA Alerts test dialog load failed", error);
      this._error = stringsFor(this.hass).loadError;
    }
    this._render();
  }

  close() {
    this.remove();
  }

  _selectedThreats() {
    return [...this.shadowRoot.querySelectorAll('input[name="threat"]:checked')].map(
      (input) => input.value
    );
  }

  _level() {
    return this.shadowRoot.querySelector("#level")?.value || "off";
  }

  _syncThreatAvailability() {
    const disabled = ["off", "clear"].includes(this._level());
    for (const input of this.shadowRoot.querySelectorAll('input[name="threat"]')) {
      input.disabled = disabled;
      if (disabled) input.checked = false;
    }
    for (const chip of this.shadowRoot.querySelectorAll(".threat-chip")) {
      chip.classList.toggle("disabled", disabled);
    }
  }

  async _set(level, threatCodes) {
    if (this._busy) return;
    this._busy = true;
    this._error = null;
    this._render();
    try {
      this._state = await this.hass.callWS({
        type: "ua_alerts/test/set",
        entry_id: this.entryId,
        level,
        threat_codes: threatCodes,
        language: this.hass.language || this.hass.locale?.language || "en",
      });
      if (level === "off") {
        this.close();
        return;
      }
    } catch (error) {
      console.error("UA Alerts test dialog save failed", error);
      this._error = stringsFor(this.hass).saveError;
    } finally {
      this._busy = false;
    }
    this._render();
  }

  _bind() {
    this.shadowRoot.querySelector(".backdrop")?.addEventListener("click", (event) => {
      if (event.target === event.currentTarget) this.close();
    });
    this.shadowRoot.querySelector("#close")?.addEventListener("click", () => this.close());
    this.shadowRoot.querySelector("#cancel")?.addEventListener("click", () => this.close());
    this.shadowRoot.querySelector("#level")?.addEventListener("change", () =>
      this._syncThreatAvailability()
    );
    this.shadowRoot.querySelector("#apply")?.addEventListener("click", () =>
      this._set(this._level(), this._selectedThreats())
    );
    this.shadowRoot.querySelector("#reset")?.addEventListener("click", () =>
      this._set("off", [])
    );
    this._syncThreatAvailability();
  }

  _render() {
    const t = stringsFor(this.hass);
    if (!this._state && !this._error) {
      this.shadowRoot.innerHTML = `${this._styles()}<div class="backdrop"><div class="dialog"><div class="loading">${t.loading}</div></div></div>`;
      this._bind();
      return;
    }

    const state = this._state || {
      location_title: this.territoryTitle || MANUFACTURER,
      level: "off",
      threat_codes: [],
      level_options: [],
      threat_options: [],
      active: false,
    };
    const chosen = new Set(state.threat_codes || []);
    const levelOptions = (state.level_options || [])
      .map(
        (option) =>
          `<option value="${escapeHtml(option.value)}" ${option.value === state.level ? "selected" : ""}>${escapeHtml(option.label)}</option>`
      )
      .join("");
    const threatOptions = (state.threat_options || [])
      .map(
        (option) => `<label class="threat-chip">
          <input type="checkbox" name="threat" value="${escapeHtml(option.value)}" ${chosen.has(option.value) ? "checked" : ""}>
          <span>${escapeHtml(option.label)}</span>
        </label>`
      )
      .join("");

    this.shadowRoot.innerHTML = `${this._styles()}
      <div class="backdrop" role="presentation">
        <section class="dialog" role="dialog" aria-modal="true" aria-label="${escapeHtml(t.title)}">
          <header>
            <div>
              <div class="title">${escapeHtml(t.title)}</div>
              <div class="territory">${escapeHtml(state.location_title || this.territoryTitle || "")}</div>
            </div>
            <button id="close" class="icon-button" type="button" aria-label="${escapeHtml(t.cancel)}">×</button>
          </header>
          ${state.active ? `<div class="active-banner">${escapeHtml(t.active)}</div>` : ""}
          ${this._error ? `<div class="error">${escapeHtml(this._error)}</div>` : ""}
          <label class="field-label" for="level">${escapeHtml(t.level)}</label>
          <select id="level" ${this._busy ? "disabled" : ""}>${levelOptions}</select>
          <div class="field-label threats-title">${escapeHtml(t.threats)}</div>
          <div class="hint">${escapeHtml(t.threatsHint)}</div>
          <div class="threats">${threatOptions}</div>
          <footer>
            <button id="reset" class="secondary" type="button" ${this._busy ? "disabled" : ""}>${escapeHtml(t.reset)}</button>
            <span class="spacer"></span>
            <button id="cancel" class="secondary" type="button" ${this._busy ? "disabled" : ""}>${escapeHtml(t.cancel)}</button>
            <button id="apply" class="primary" type="button" ${this._busy ? "disabled" : ""}>${escapeHtml(t.apply)}</button>
          </footer>
        </section>
      </div>`;
    this._bind();
  }

  _styles() {
    return `<style>
      :host { font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif); color: var(--primary-text-color); }
      .backdrop { position: fixed; inset: 0; z-index: 10000; display: flex; align-items: center; justify-content: center; padding: 24px; background: rgba(0,0,0,.48); box-sizing: border-box; }
      .dialog { width: min(620px, 100%); max-height: min(760px, calc(100vh - 48px)); overflow: auto; box-sizing: border-box; padding: 22px; border-radius: 20px; background: var(--card-background-color, var(--ha-card-background, #fff)); box-shadow: 0 12px 40px rgba(0,0,0,.35); }
      header { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 18px; }
      .title { font-size: 22px; font-weight: 600; line-height: 1.25; }
      .territory { margin-top: 4px; color: var(--secondary-text-color); font-size: 14px; }
      .icon-button { margin-left: auto; border: 0; background: transparent; color: var(--primary-text-color); font-size: 30px; line-height: 28px; cursor: pointer; }
      .active-banner { margin: 0 0 16px; padding: 10px 12px; border-radius: 10px; background: var(--warning-color, #ffa600); color: var(--text-primary-color, #111); font-weight: 500; }
      .error { margin: 0 0 16px; padding: 10px 12px; border-radius: 10px; background: var(--error-color, #db4437); color: #fff; }
      .field-label { display: block; margin: 14px 0 7px; font-weight: 600; }
      select { width: 100%; box-sizing: border-box; padding: 11px 12px; border: 1px solid var(--divider-color); border-radius: 10px; background: var(--card-background-color, #fff); color: var(--primary-text-color); font: inherit; }
      .threats-title { margin-bottom: 2px; }
      .hint { margin-bottom: 10px; color: var(--secondary-text-color); font-size: 13px; }
      .threats { display: flex; flex-wrap: wrap; gap: 8px; }
      .threat-chip { position: relative; cursor: pointer; }
      .threat-chip input { position: absolute; opacity: 0; pointer-events: none; }
      .threat-chip span { display: inline-block; padding: 8px 11px; border: 1px solid var(--divider-color); border-radius: 999px; background: var(--card-background-color, #fff); user-select: none; }
      .threat-chip input:checked + span { border-color: var(--primary-color); background: color-mix(in srgb, var(--primary-color) 16%, transparent); color: var(--primary-text-color); }
      .threat-chip.disabled { opacity: .45; cursor: default; }
      footer { display: flex; align-items: center; gap: 10px; margin-top: 24px; }
      .spacer { flex: 1; }
      footer button { border: 0; border-radius: 18px; padding: 9px 16px; font: inherit; font-weight: 600; cursor: pointer; }
      footer button:disabled { opacity: .55; cursor: default; }
      .primary { background: var(--primary-color); color: var(--text-primary-color, #fff); }
      .secondary { background: transparent; color: var(--primary-color); }
      .loading { padding: 28px 8px; text-align: center; color: var(--secondary-text-color); }
      @media (max-width: 600px) {
        .backdrop { align-items: flex-end; padding: 0; }
        .dialog { width: 100%; max-height: 88vh; border-radius: 20px 20px 0 0; padding: 18px; }
        footer { flex-wrap: wrap; }
        .spacer { display: none; }
        footer button { flex: 1 1 auto; }
      }
    </style>`;
  }
}

if (!customElements.get("ua-alerts-test-dialog")) {
  customElements.define("ua-alerts-test-dialog", UAAlertsTestDialog);
}

function openTestDialog(hass, entryId, territoryTitle) {
  document.querySelector("ua-alerts-test-dialog")?.remove();
  const dialog = document.createElement("ua-alerts-test-dialog");
  dialog.hass = hass;
  dialog.entryId = entryId;
  dialog.territoryTitle = territoryTitle;
  document.body.append(dialog);
}

function uaEntryId(page, device) {
  const ids = device?.config_entries || [];
  const entries = page?.entries || [];
  const match = ids.find((id) => entries.some((entry) => entry.entry_id === id && entry.domain === DOMAIN));
  return match || device?.primary_config_entry || ids[0];
}

function addTestDeviceAction(page) {
  const hass = page?.hass;
  const device = hass?.devices?.[page?.deviceId];
  if (!hass?.user?.is_admin || !device || device.manufacturer !== MANUFACTURER) return;

  const actions = [...(page._deviceActions || [])];
  if (actions.some((action) => action?.uaAlertsTestAction)) return;

  const configIndex = actions.findIndex(
    (action) => typeof action?.href === "string" && action.href.includes(`/config/integrations/integration/${DOMAIN}`)
  );
  if (configIndex < 0) return;

  const entryId = uaEntryId(page, device);
  if (!entryId) return;

  const territoryTitle =
    page?.entries?.find((entry) => entry.entry_id === entryId)?.title ||
    device.name_by_user ||
    device.name ||
    MANUFACTURER;
  const base = actions[configIndex];
  actions[configIndex] = {
    ...base,
    label: `${base.label || MANUFACTURER} · ${territoryTitle}`,
  };
  const testAction = {
    ...base,
    uaAlertsTestAction: true,
    href: undefined,
    target: undefined,
    trailingIcon: undefined,
    label: stringsFor(hass).action,
    action: () => openTestDialog(hass, entryId, territoryTitle),
  };

  // Keep the original configuration action immediately after the prominent test
  // button, so Configure remains available from the device-page overflow menu.
  page._deviceActions = [testAction, ...actions];
}

async function patchDevicePage() {
  await customElements.whenDefined("ha-config-device-page");
  const klass = customElements.get("ha-config-device-page");
  const proto = klass?.prototype;
  if (!proto || proto[PATCH_MARK]) return;

  const original = proto._getDeviceActions;
  if (typeof original !== "function") {
    console.warn("UA Alerts: Home Assistant device action hook not found");
    return;
  }

  proto._getDeviceActions = async function (...args) {
    const result = await original.apply(this, args);
    try {
      addTestDeviceAction(this);
    } catch (error) {
      console.warn("UA Alerts: could not add device test action", error);
    }
    return result;
  };

  Object.defineProperty(proto, PATCH_MARK, { value: true });
}

patchDevicePage().catch((error) =>
  console.warn("UA Alerts: frontend helper initialization failed", error)
);
