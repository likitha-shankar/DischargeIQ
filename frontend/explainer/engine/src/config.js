/**
 * File: frontend/explainer/engine/src/config.js
 * Component: Anatomy Explainer — Config Loader
 * Description: Parses the explainer config from three sources in priority order:
 *   1. window.__DISCHARGEIQ_CONFIG__ (set by parent before script loads — preferred).
 *   2. URL query param ?config=<base64url-encoded-JSON> (works for Streamlit iframes
 *      where postMessage timing is uncertain).
 *   3. window.addEventListener('message') for late-arriving postMessage from parent
 *      (Flutter WebView JS channel or Streamlit postMessage).
 *
 * The config drives one explainer instance: which model to load, which panels to
 * show, what captions and safety lines to display, and whether voice is enabled.
 *
 * Dependencies: none (pure DOM + JSON)
 * Consumed by: src/main.js
 */

/** @typedef {import('./types.js').ExplainerConfig} ExplainerConfig */

/**
 * Default config used when no field is supplied by the parent.
 * Ensures the engine never crashes due to missing optional fields.
 *
 * @type {Partial<ExplainerConfig>}
 */
const DEFAULTS = {
  language: 'en',
  title: 'Anatomy Explainer',
  subtitle: '',
  panels: [],
  safety_lines: [],
  footer: 'This explanation is based on your discharge papers and reviewed by a clinician. Not medical advice.',
  voice: { enabled: false, panel_texts: [] },
};

/**
 * Attempt to read the config injected into window by the parent page.
 *
 * Streamlit sets window.__DISCHARGEIQ_CONFIG__ in the iframe srcdoc before
 * this script loads. Flutter injects it via evaluateJavascript before the page
 * renders. Returns null when the property is absent or not an object.
 *
 * @returns {ExplainerConfig|null}
 */
function _readWindowConfig() {
  const raw = window.__DISCHARGEIQ_CONFIG__;
  if (raw && typeof raw === 'object') {
    return raw;
  }
  return null;
}

/**
 * Attempt to parse the config from the ?config= URL query parameter.
 *
 * The value is expected to be base64url-encoded JSON. Used when the parent
 * cannot inject window.__DISCHARGEIQ_CONFIG__ before page load (e.g. a plain
 * <iframe src="..."> with a URL the parent controls but not the srcdoc).
 *
 * @returns {ExplainerConfig|null}
 */
function _readQueryConfig() {
  try {
    const params = new URLSearchParams(window.location.search);
    const encoded = params.get('config');
    if (!encoded) return null;
    const json = atob(encoded.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(json);
  } catch (err) {
    console.warn('[DischargeIQ] Failed to parse ?config= query param:', err);
    return null;
  }
}

/**
 * Merge a raw config object with DEFAULTS, filling in any missing fields.
 *
 * Shallow merge: top-level keys in raw override DEFAULTS. Nested objects
 * (e.g. voice) are replaced wholesale, not deeply merged.
 *
 * @param {object} raw - Raw config received from any source.
 * @returns {ExplainerConfig} - Merged config safe to pass to the engine.
 */
function _applyDefaults(raw) {
  return { ...DEFAULTS, ...raw };
}

/**
 * Register a one-time message listener for late-arriving postMessage configs.
 *
 * The Flutter WebView JS channel and Streamlit postMessage both arrive after
 * the page renders. This allows the engine to receive config asynchronously.
 * Calls `onConfig` once with the parsed config; unregisters itself after.
 *
 * @param {function(ExplainerConfig): void} onConfig - Called when config arrives.
 */
function listenForPostMessageConfig(onConfig) {
  function handler(event) {
    if (!event.data || event.data.type !== 'DISCHARGEIQ_CONFIG') return;
    window.removeEventListener('message', handler);
    try {
      const config = _applyDefaults(event.data.payload);
      onConfig(config);
    } catch (err) {
      console.error('[DischargeIQ] Failed to parse postMessage config:', err);
    }
  }
  window.addEventListener('message', handler);
}

/**
 * Load the explainer config synchronously from available sources.
 *
 * Checks window.__DISCHARGEIQ_CONFIG__ first (fastest, most reliable), then
 * falls back to URL query param decoding. Returns null if neither source
 * provides a config — callers should then call listenForPostMessageConfig()
 * and wait for a late-arriving config.
 *
 * @returns {ExplainerConfig|null} - Merged config, or null if not yet available.
 */
function loadConfigSync() {
  const fromWindow = _readWindowConfig();
  if (fromWindow) return _applyDefaults(fromWindow);

  const fromQuery = _readQueryConfig();
  if (fromQuery) return _applyDefaults(fromQuery);

  return null;
}

export { loadConfigSync, listenForPostMessageConfig };
