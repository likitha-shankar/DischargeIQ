"""
File: streamlit_app.py
Owner: Likitha Shankar
Description: Streamlit frontend for DischargeIQ — renders the upload screen,
  drives the PDF analysis pipeline via POST /analyze to the FastAPI backend,
  and displays a 6-tab summary screen (What Happened, Medications, Appointments,
  Warning Signs, Recovery, AI Review). All persistent UI elements (header, tab
  bar, chat panel, PDF modal) are injected into window.parent.document so they
  survive Streamlit reruns. State transitions route through hidden Streamlit
  buttons whose clicks are forwarded from the visible parent-DOM UI via JS
  .click(), preserving Streamlit's native button state-management semantics.
Key functions/classes:
  _render_upload_screen        — upload zone, drag-and-drop, Get Started button
  _render_summary_screen       — tab host, citation modal, beforeunload warning
  _render_app_header           — sticky teal header with logo + action buttons
  _render_tab_bar              — horizontal tab bar injected above main content
  _inject_global_css           — shared CSS injected once per session
  _pipeline_loading_visual_html — animated progress bar iframe during analysis
  _render_section_diagnosis    — What Happened tab (Agent 2 output + DX badges)
  _render_section_medications  — Medications tab (Agent 3 output + med cards)
  _render_section_appointments — Appointments tab (sorted, with SVG calendar)
  _render_section_warning_signs — Warning Signs tab (Agent 5 escalation tiers)
  _render_section_recovery     — Recovery tab (Agent 4 timeline)
  _render_section_simulator    — AI Review tab (Agent 6 gap score + concepts)
  _citation_button             — p.N chip that opens PDF modal at source page
  _render_appointment_row      — single appointment card with date + citation
Edge cases handled:
  - pipeline_status partial/complete_with_warnings: section-level warning banners
  - Citation modal: opens PDF at correct page; clears pending state after one rerun
  - Progress bar: indet shuttle → nudge crawl → abort on result; watchdog fallback
  - beforeunload: warns patient before browser refresh wipes results
  - Logo click: navigates to What Happened tab from any tab
  - Agent 6 tab: graceful fallback message if simulator was skipped or failed
  - Dark-mode toggle on upload screen preserved across reruns via session state
Dependencies: streamlit, requests, dischargeiq.utils.logger.
  Backend (FastAPI) must be running at API_BASE_URL (default http://127.0.0.1:8000).
Called by: start.sh / start.bat via `streamlit run streamlit_app.py`;
  also compatible with Streamlit Cloud and any reverse-proxy deployment.
"""

import base64
import html
import json
import logging
import os
import re
import uuid

import requests
import streamlit as st
from dotenv import load_dotenv

from dischargeiq.utils.logger import configure_logging
from dischargeiq.utils.questions_html import build_copy_button_html, build_questions_section_html

load_dotenv(dotenv_path=".env")
configure_logging()

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
_ANALYZE_URL = f"{_API_BASE}/analyze"
_CHAT_URL = f"{_API_BASE}/chat"

# Left-border colors for medication cards.
_MED_BORDER = {
    "new": "#185FA5",
    "changed": "#BA7517",
    "continued": "#3B6D11",
    "discontinued": "#A32D2D",
}

# Session state keys — defined as constants to avoid typos across functions.
_S_RESULT = "result"
_S_PDF_BYTES = "pdf_bytes"
_S_PDF_SESSION_ID = "pdf_session_id"
_S_FILE_NAME = "file_name"
_S_ACTIVE_TAB = "active_tab"              # Which tab is currently visible.
_S_PENDING_CITATION = "pending_citation"  # One-shot trigger to open PDF modal.
_S_BOOTSTRAPPED = "session_bootstrapped"  # True after one-shot refresh cleanup has run.
_S_LOADING_SHOWN = "upload_loading_shown" # Two-pass loading animation flag.
_S_UPLOAD_DARK = "upload_dark_mode"       # Light/dark toggle on upload page.
_S_STAGED_PDF_BYTES = "staged_pdf_bytes"  # Bytes stored before rerun for Pass 2.
_S_STAGED_PDF_NAME = "staged_pdf_name"    # Filename stored before rerun for Pass 2.
_S_UPLOAD_ERROR = "upload_error"          # One-shot error message shown on upload screen.
_S_TOUR_REPLAY = "tour_replay_pending"    # One-shot flag — force the guided tour to start.
_S_PDF_MODAL_NONCE = "pdf_modal_nonce"    # Bumped each time the PDF modal is opened.
_S_LANDING_DONE = "landing_intro_done"    # Cinematic landing intro completed for this Streamlit session.

# DOM element ids we inject into window.parent.document.  Shared by the
# one-shot refresh cleanup and the "Upload new" cleanup so both stay in sync.
_DIQ_PARENT_DOM_IDS = [
    "diq-app-header", "diq-app-header-styles",
    "diq-tab-bar", "diq-tab-bar-styles",
    "diq-pdf-modal", "diq-pdf-modal-styles",
    "diq-panel-root", "diq-panel-styles",
    "diq-chat-bubble",
]

# Tab definitions — (key, human label). Order is render order.
_TABS = [
    ("diagnosis", "What happened"),
    ("medications", "Medications"),
    ("appointments", "Appointments"),
    ("warnings", "Warning signs"),
    ("recovery", "Recovery"),
    ("simulator", "AI Review"),
]

# Inline SVG calendar icon used in appointment date rows.  Stroke-only, 13 px,
# teal (#1D9E75) to match the appointment dot colour.  Replaces the 📅 emoji
# which renders as a bulky torn-calendar image in most browsers.
_CAL_ICON_SVG = (
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" '
    'stroke="#1D9E75" stroke-width="2.2" stroke-linecap="round" '
    'stroke-linejoin="round" '
    'style="vertical-align:-1px;margin-right:3px;display:inline;">'
    '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>'
    '<line x1="16" y1="2" x2="16" y2="6"></line>'
    '<line x1="8" y1="2" x2="8" y2="6"></line>'
    '<line x1="3" y1="10" x2="21" y2="10"></line>'
    '</svg>'
)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="DischargeIQ",
    page_icon=":hospital:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Session state bootstrap ───────────────────────────────────────────────────

for _key, _default in [
    (_S_RESULT, None),
    (_S_PDF_BYTES, None),
    (_S_PDF_SESSION_ID, None),
    (_S_FILE_NAME, "document.pdf"),
    (_S_ACTIVE_TAB, "diagnosis"),
    (_S_PENDING_CITATION, None),
    (_S_BOOTSTRAPPED, False),
    (_S_LOADING_SHOWN, False),
    (_S_UPLOAD_DARK, False),
    (_S_STAGED_PDF_BYTES, None),
    (_S_STAGED_PDF_NAME, "document.pdf"),
    (_S_UPLOAD_ERROR, None),
    (_S_TOUR_REPLAY, False),
    (_S_PDF_MODAL_NONCE, 0),
    (_S_LANDING_DONE, False),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default


# ── Loading animation ─────────────────────────────────────────────────────────


def _pipeline_loading_visual_html(progress_url: str) -> str:
    """
    Return a complete HTML document for the loading takeover.

    Rendered via st.components.v1.html() so scripts execute. On load the JS
    expands the iframe to cover the full browser viewport (Option A — full-page
    takeover: white card centred on #F5F4F1). Avoids st.markdown() sanitisation
    which strips <style> and mangles nested elements inside containers.

    Real-time progress: the JS polls `progress_url` every 800 ms and lights up
    pills, advances the progress bar, and swaps the status text based on
    `current_agent` and `message` from the backend's /progress endpoint. This
    replaces the old purely time-based animation, which lied about progress
    on slow LLM responses.

    The hospital→home walking scene is still CSS-only and decorative.

    Args:
        progress_url: Absolute URL the iframe should poll, typically
                      f"{_API_BASE}/progress/{pdf_session_id}".

    Returns:
        str: Complete <!DOCTYPE html> document string.
    """
    template = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<script>
(function() {
  function expand() {
    var f = window.frameElement;
    if (!f) return;
    // Expand iframe to cover the full viewport
    var s = f.style;
    s.position = 'fixed';
    s.inset = '0';
    s.width = '100vw';
    s.height = '100vh';
    s.zIndex = '9998';
    s.border = 'none';
    s.margin = '0';
    s.padding = '0';
    // Suppress Streamlit chrome in the parent document
    var pdoc = window.parent.document;
    if (!pdoc.getElementById('diq-pl-parent-style')) {
      var el = pdoc.createElement('style');
      el.id = 'diq-pl-parent-style';
      el.textContent =
        'header[data-testid="stHeader"]{display:none!important}' +
        'footer{display:none!important}' +
        'div[data-testid="stDecoration"]{display:none!important}';
      pdoc.head.appendChild(el);
    }
  }
  // Run immediately (before DOM ready) and again on load
  expand();
  window.addEventListener('load', expand);
})();
</script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{
  width:100%;height:100%;
  background:#F5F4F1;
  display:flex;align-items:center;justify-content:center;
  font-family:Calibri,'Carlito','Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;
}
/* keyframes */
@keyframes diq-walk{0%{left:74px;opacity:1}65%{left:200px;opacity:1}85%{left:218px;opacity:.5}100%{left:230px;opacity:0}}
@keyframes diq-doc{0%{left:76px;opacity:0;transform:translateY(2px) rotate(0deg)}12%{opacity:1;transform:translateY(-10px) rotate(-6deg)}60%{left:198px;opacity:1;transform:translateY(-14px) rotate(4deg)}80%{left:215px;opacity:.4;transform:translateY(-8px) rotate(0deg)}100%{left:228px;opacity:0;transform:translateY(4px) rotate(0deg)}}
@keyframes diq-ll{from{transform:rotate(-18deg)}to{transform:rotate(18deg)}}
@keyframes diq-lr{from{transform:rotate(18deg)}to{transform:rotate(-18deg)}}
@keyframes diq-pulse{0%,100%{opacity:1}50%{opacity:.55}}
@keyframes diq-indet{0%{margin-left:-30%;width:30%}100%{margin-left:100%;width:30%}}

.wrap{background:#fff;border-radius:20px;padding:32px 40px;display:flex;flex-direction:column;align-items:center;gap:16px;box-shadow:0 4px 32px rgba(0,0,0,.08);max-width:540px;width:90%}
.ttl{font-size:20px;font-weight:700;color:#0A2A1F;text-align:center}
.sub{font-size:13px;color:#64748B;text-align:center;max-width:360px;line-height:1.55}

.scene{position:relative;width:280px;height:110px;margin:4px auto 0}
.gnd{position:absolute;bottom:0;left:0;right:0;height:2px;background:#9FD9C8;border-radius:1px}
.road{position:absolute;bottom:10px;left:72px;right:48px;border-top:1.5px dashed #9FD9C8}

.hosp{position:absolute;left:6px;bottom:2px;width:64px;height:76px}
.roof{position:relative;height:18px;width:100%;background:#0F6E56;border-radius:4px 4px 0 0}
.cv{position:absolute;left:50%;top:50%;width:3px;height:10px;background:#fff;transform:translate(-50%,-50%);border-radius:1px}
.ch{position:absolute;left:50%;top:50%;width:10px;height:3px;background:#fff;transform:translate(-50%,-50%);border-radius:1px}
.hb{position:relative;height:58px;width:100%;background:#E1F5EE;border:1.5px solid #9FD9C8;border-top:none}
.win{position:absolute;width:10px;height:9px;background:#9FD9C8;border-radius:1px}
.w1{top:6px;left:6px}.w2{top:6px;right:6px}.w3{top:22px;left:6px}.w4{top:22px;right:6px}
.door{position:absolute;bottom:0;left:calc(50% - 7px);width:14px;height:20px;background:#0F6E56;border-radius:2px 2px 0 0}

.person{position:absolute;bottom:2px;width:20px;height:36px;animation:diq-walk 5s linear infinite}
.ph{width:12px;height:12px;border-radius:50%;background:#1D9E75;margin:0 auto}
.pt{width:9px;height:14px;background:#0F6E56;margin:1px auto 0;border-radius:2px 2px 0 0}
.pl{display:flex;flex-direction:row;gap:2px;justify-content:center}
.pll{width:4px;height:7px;background:#085041;border-radius:0 0 2px 2px;transform-origin:top center;animation:diq-ll .45s ease-in-out infinite alternate}
.plr{width:4px;height:7px;background:#085041;border-radius:0 0 2px 2px;transform-origin:top center;animation:diq-lr .45s ease-in-out infinite alternate}

.doc{position:absolute;bottom:22px;width:16px;height:20px;background:#fff;border:1.5px solid #9FD9C8;border-radius:2px;padding:3px 2px;animation:diq-doc 5s linear infinite}
.dl{height:2px;background:#9FD9C8;border-radius:1px;margin-bottom:2px}
.dl:last-child{margin-bottom:0}
.ds{width:70%}
.home{position:absolute;right:2px;bottom:2px;width:36px;height:36px}

.status{font-size:11px;font-weight:500;color:#0F6E56;text-align:center;animation:diq-pulse 2s ease-in-out infinite}
.bar{width:100%;max-width:320px;height:4px;background:#E1F5EE;border-radius:4px;overflow:hidden;position:relative}
/* Width is driven by JS (data.current_agent / 6). Transition gives a smooth
   slide each time the backend reports a new agent step. While we have no
   progress yet, .indet is added and a CSS-only shuttle animates inside the
   bar so the user sees motion even before the first agent ticks. */
.fill{height:100%;background:#0F6E56;border-radius:4px;width:0%;transition:width .5s ease-out}
.fill.indet{width:30%!important;animation:diq-indet 1.4s ease-in-out infinite;transition:none}
.pills{display:flex;flex-wrap:wrap;justify-content:center;gap:6px;max-width:380px}
.pill{font-size:10px;font-weight:500;padding:4px 10px;border-radius:999px;border:1px solid #9FD9C8;color:#0F6E56;background:#fff;opacity:.35;transition:background .25s,color .25s,border-color .25s,opacity .25s}
.pill.active{background:#0F6E56;color:#fff;border-color:#0F6E56;opacity:1}
.pill.current{box-shadow:0 0 0 2px rgba(15,110,86,0.18);animation:diq-pulse 1.6s ease-in-out infinite}
</style>
</head>
<body>
<div class="wrap">
  <p class="ttl">Analyzing your discharge document</p>
  <p class="sub">Our AI agents are reading your document &mdash; this takes about 30 seconds</p>
  <div class="scene">
    <div class="gnd"></div><div class="road"></div>
    <div class="hosp">
      <div class="roof"><div class="cv"></div><div class="ch"></div></div>
      <div class="hb">
        <div class="win w1"></div><div class="win w2"></div>
        <div class="win w3"></div><div class="win w4"></div>
        <div class="door"></div>
      </div>
    </div>
    <div class="person">
      <div class="ph"></div><div class="pt"></div>
      <div class="pl"><div class="pll"></div><div class="plr"></div></div>
    </div>
    <div class="doc">
      <div class="dl"></div><div class="dl ds"></div>
      <div class="dl"></div><div class="dl ds"></div>
    </div>
    <svg class="home" viewBox="0 0 24 24" fill="none">
      <path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z" stroke="#0F6E56" stroke-width="1.4"/>
      <path d="M9 21V12h6v9" stroke="#0F6E56" stroke-width="1.4"/>
    </svg>
  </div>
  <p class="status" id="diq-status">Starting analysis&hellip;</p>
  <div class="bar"><div class="fill indet" id="diq-fill"></div></div>
  <div class="pills">
    <span class="pill" data-step="1">Extraction</span>
    <span class="pill" data-step="2">Diagnosis</span>
    <span class="pill" data-step="3">Medications</span>
    <span class="pill" data-step="4">Recovery</span>
    <span class="pill" data-step="5">Warning signs</span>
    <span class="pill" data-step="6">Discharge check</span>
  </div>
</div>
<script>
(function() {
  // Poll the backend's /progress/{session_id} endpoint and reflect the real
  // agent state in the bar, status text, and pill highlights. Replaces the
  // old time-based animation that lied about progress on slow LLM responses.
  var PROGRESS_URL = "__DIQ_PROGRESS_URL__";
  var TOTAL_STEPS  = 6;
  var POLL_MS      = 800;     // tick interval
  var FETCH_MS     = 6000;    // per-fetch timeout — abort hung requests
  var WATCHDOG_MS  = 4000;    // swap to "server is busy" if no update lands

  // Optional debug logging — append ?diqDebug=1 to the URL.
  var DEBUG = false;
  try { DEBUG = /[?&]diqDebug=1/.test(window.parent.location.search); } catch(e) {}
  function log() {
    if (!DEBUG) return;
    try { console.log.apply(console, ['[diq progress]'].concat([].slice.call(arguments))); }
    catch(e) {}
  }

  var statusEl = document.getElementById('diq-status');
  var fillEl   = document.getElementById('diq-fill');
  var pills    = Array.prototype.slice.call(document.querySelectorAll('.pill'));
  var lastStep            = -1;
  var lastSuccessAt       = Date.now();
  var lastUserMessage     = null;
  var watchdogActive      = false;
  var inFlightController  = null;
  var targetPct           = 0;      // last confirmed % from backend poll
  var simPct              = 1;      // visual position; seeded at 1 to match initial HTML width
  var MAX_LEAD            = (100 / TOTAL_STEPS) * 0.65;

  log('starting poll loop, url=' + PROGRESS_URL);

  // Nudge bar forward 0.4 pp every 250 ms so the user sees continuous motion
  // between real poll ticks. Capped at targetPct + MAX_LEAD so simulated
  // progress never races more than ~65% of one step ahead of reality.
  setInterval(function() {
    if (fillEl.classList.contains('indet')) return;
    var cap = Math.min(targetPct + MAX_LEAD, 99);
    if (simPct < cap) {
      simPct = Math.min(simPct + 0.4, cap);
      fillEl.style.width = simPct.toFixed(1) + '%';
    }
  }, 250);

  function applyStep(n, message) {
    n = Math.max(0, Math.min(TOTAL_STEPS, n | 0));
    if (n > 0) {
      if (fillEl.classList.contains('indet')) {
        // Watchdog had re-added indet. Snap to simPct with no transition so
        // the bar doesn't slide backward from the shuttle before advancing.
        fillEl.style.transition = 'none';
        fillEl.classList.remove('indet');
        fillEl.style.width = simPct.toFixed(1) + '%';
        requestAnimationFrame(function() {
          requestAnimationFrame(function() { fillEl.style.transition = ''; });
        });
      }
      var realPct = (n / TOTAL_STEPS) * 100;
      targetPct = realPct;
      simPct = Math.max(simPct, realPct);  // never go backward
      // Nudge will update width on the next 250 ms tick — avoids a hard jump
    }
    pills.forEach(function(p) {
      var step = parseInt(p.getAttribute('data-step'), 10);
      p.classList.toggle('active',  step <= n && n > 0);
      p.classList.toggle('current', step === n && n > 0 && n < TOTAL_STEPS + 1);
    });
    if (message) {
      statusEl.textContent = message;
      lastUserMessage = message;
    }
    watchdogActive = false;
  }

  function applyComplete(message) {
    if (fillEl.classList.contains('indet')) {
      fillEl.style.transition = 'none';
      fillEl.classList.remove('indet');
      fillEl.style.width = simPct.toFixed(1) + '%';
      requestAnimationFrame(function() {
        requestAnimationFrame(function() { fillEl.style.transition = ''; });
      });
    }
    targetPct = 100;
    simPct = 100;
    fillEl.style.width = '100%';
    pills.forEach(function(p) {
      p.classList.add('active');
      p.classList.remove('current');
    });
    statusEl.textContent = message || 'Almost ready…';
    watchdogActive = false;
  }

  function applyWatchdog() {
    // Fires when no successful poll has landed for WATCHDOG_MS. The bar stays
    // where it was; we just swap the status text so the user knows the UI
    // hasn't frozen — the backend is busy on a long agent step.
    if (watchdogActive) return;
    watchdogActive = true;
    statusEl.textContent =
      'Server is busy — still analyzing your document…';
    // Re-show the indeterminate shuttle so there's visible motion even when
    // the bar's deterministic width can't advance.
    if (!fillEl.classList.contains('indet')) {
      fillEl.classList.add('indet');
    }
  }

  async function poll() {
    // Abort any prior in-flight fetch so we never have two concurrent
    // requests competing for the event loop.
    if (inFlightController) {
      try { inFlightController.abort(); } catch(e) {}
    }
    var controller = new AbortController();
    inFlightController = controller;
    var fetchTimer = setTimeout(function() { controller.abort(); }, FETCH_MS);

    try {
      var r = await fetch(PROGRESS_URL, {
        cache: 'no-store',
        signal: controller.signal,
      });
      clearTimeout(fetchTimer);
      if (!r.ok) { log('fetch !ok', r.status); return; }
      var data = await r.json();
      if (!data) return;
      log('poll', data);

      lastSuccessAt = Date.now();

      if (data.status === 'complete') { applyComplete(data.message); return; }
      if (data.status === 'error')    {
        statusEl.textContent = data.message || 'Analysis failed.';
        return;
      }
      if (data.status === 'not_found') {
        // Backend hasn't recorded progress yet — leave the indeterminate
        // shuttle running and keep polling.
        return;
      }
      var n = data.current_agent || 0;
      if (n !== lastStep) lastStep = n;
      applyStep(n, data.message);
    } catch(e) {
      clearTimeout(fetchTimer);
      log('fetch error', e && e.name);
      // Network blip / abort / CORS — try again on the next tick.
    } finally {
      if (inFlightController === controller) inFlightController = null;
    }
  }

  function watchdog() {
    if (Date.now() - lastSuccessAt > WATCHDOG_MS) applyWatchdog();
  }

  poll();
  setInterval(poll, POLL_MS);
  setInterval(watchdog, 1000);
})();
</script>
</body>
</html>"""
    return template.replace("__DIQ_PROGRESS_URL__", progress_url)


# ── Global CSS ────────────────────────────────────────────────────────────────

def _inject_global_css() -> None:
    """
    Inject the locked light-theme CSS and component styles used across
    the summary screen.

    The injected app header and tab bar live in window.parent.document
    and carry their own scoped styles — this function only covers the
    Streamlit-rendered content inside stMain plus the hidden-button
    collapse trick used by header/tab-bar/reset interactions.
    """
    st.markdown(
        """
        <style>
        /* ── Typography ─────────────────────────────────────────────────────── */
        /* Project-wide font is Calibri, with web-safe fallbacks. Calibri is
           shipped on Windows; "Carlito" is the open-source Calibri-metric-
           compatible font available via Google Fonts so non-Windows users
           (Mac, Linux, Chromebook) still see the same letter shapes and
           spacing. Final fallbacks are system humanist sans-serifs. */
        @import url('https://fonts.googleapis.com/css2?family=Carlito:ital,wght@0,400;0,700;1,400;1,700&display=swap');

        html, body, .stApp, .stMarkdown, p, li, span, div, button, input,
        h1, h2, h3, h4, h5, h6, label, textarea, select {
            font-family: Calibri, 'Carlito', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif !important;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        p, li, span, div, button, input, label, textarea, select {
            font-size: 1.05rem;
            line-height: 1.55;
        }

        /* ── Page background ─────────────────────────────────────────────────── */
        .stApp {
            background: linear-gradient(160deg, #f0fdf8 0%, #f8fafc 55%, #eef7f4 100%) !important;
            background-attachment: fixed !important;
        }
        .block-container {
            padding-top: 0.5rem !important;
            padding-bottom: 2rem !important;
            max-width: 100% !important;
        }

        /* Custom scrollbar */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 6px; }
        ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

        /* Hide Streamlit's native top toolbar ("Deploy" button etc.) so
           our teal app header is not covered by it. */
        header[data-testid="stHeader"] { display: none !important; }

        /* Clear vertical space for the 56px teal app header + ~40px tab
           bar that live outside stMain in window.parent.document.
           Trimmed from 104px to 92px to bring section content closer
           to the tab bar (was visibly too generous). */
        section[data-testid="stMain"] { padding-top: 92px !important; }

        /* Streamlit's default block-container adds ~6rem of top padding
           even after the stMain override; collapse it so the tab bar
           sits right above the section title. */
        section[data-testid="stMain"] .block-container {
            padding-top: 0.5rem !important;
        }

        /* Remove Streamlit's default top padding on columns */
        [data-testid="column"] { padding: 0 8px; }

        /* ── Custom collapsible details ────────────────────────────────────
           We use native HTML5 <details> for static expandable content (e.g.
           the medication rationale, "Questions answered" list). This bypasses
           Streamlit 1.56's broken Material Symbols chevron entirely. The
           summary draws its own CSS triangle that rotates 90° when open. */
        details.diq-html-details {
            background: #ffffff;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            margin: 6px 0 12px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        }
        details.diq-html-details > summary {
            list-style: none;
            cursor: pointer;
            padding: 10px 14px;
            font-size: 0.88rem;
            font-weight: 600;
            color: #1E293B;
            display: flex;
            align-items: center;
            user-select: none;
        }
        details.diq-html-details > summary::-webkit-details-marker {
            display: none;
        }
        details.diq-html-details > summary::before {
            content: "";
            display: inline-block;
            width: 0; height: 0;
            border-left: 6px solid #475569;
            border-top: 5px solid transparent;
            border-bottom: 5px solid transparent;
            margin-right: 10px;
            transition: transform 0.18s ease;
            flex-shrink: 0;
        }
        details.diq-html-details[open] > summary::before {
            transform: rotate(90deg);
        }
        details.diq-html-details > .diq-html-details-body {
            padding: 4px 16px 14px;
            font-size: 0.88rem;
            color: #334155;
            line-height: 1.55;
            border-top: 1px solid #F1F5F9;
        }
        details.diq-html-details > .diq-html-details-body p { margin: 0 0 0.5em; }
        details.diq-html-details > .diq-html-details-body ul { margin: 0.25em 0; padding-left: 18px; }
        details.diq-html-details > .diq-html-details-body li { margin-bottom: 3px; }

        /* ── Citation chip styling ─────────────────────────────────────────
           Streamlit puts each widget's key onto its container as a class
           (e.g. `st-key-cite_med_0`). All citation buttons use keys that
           start with `cite_`, so this selector targets ONLY citation
           buttons and leaves other Streamlit buttons (toggles, primary
           CTAs) untouched. */
        /* ── Verify-extraction expander — match diq-html-details style ──────────
           st.expander renders as a native <details> element. We override its
           default Streamlit styling so it looks identical to the medication
           rationale toggle (diq-html-details): white card, grey border,
           rounded corners, bold summary text, separator line on body. */
        [data-testid="stExpander"] details {
            background: #ffffff !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 10px !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
            margin: 6px 0 12px !important;
        }
        [data-testid="stExpander"] details summary {
            padding: 10px 14px !important;
            font-size: 0.88rem !important;
            font-weight: 600 !important;
            color: #1E293B !important;
            list-style: none !important;
            display: flex !important;
            align-items: center !important;
        }
        [data-testid="stExpander"] details summary::-webkit-details-marker {
            display: none !important;
        }
        [data-testid="stExpander"] details summary [data-testid="stExpanderToggleIcon"],
        [data-testid="stExpander"] details summary [data-testid="stIconMaterial"],
        [data-testid="stExpander"] details summary svg {
            display: none !important;
        }
        [data-testid="stExpander"] details summary::before {
            content: "";
            display: inline-block;
            width: 0; height: 0;
            border-left: 6px solid #475569;
            border-top: 5px solid transparent;
            border-bottom: 5px solid transparent;
            margin-right: 5px;
            transition: transform 0.18s ease;
            flex-shrink: 0;
        }
        [data-testid="stExpander"] details[open] summary::before {
            transform: rotate(90deg);
        }
        [data-testid="stExpander"] details[open] > div {
            border-top: 1px solid #F1F5F9 !important;
            padding: 0 16px 14px !important;
        }
        [data-testid="stExpander"] details[open] > div > div:first-child,
        [data-testid="stExpander"] details[open] [data-testid="stVerticalBlock"]:first-child,
        [data-testid="stExpander"] details[open] > div > div:first-child > div:first-child {
            padding-top: 0 !important;
            margin-top: 0 !important;
        }
        [data-testid="stExpander"] details[open] p:first-child,
        [data-testid="stExpander"] details[open] small:first-child {
            margin-top: 0 !important;
            padding-top: 0 !important;
        }

        [class*="st-key-cite_"] button {
            padding: 1px 10px !important;
            font-size: 0.72rem !important;
            font-weight: 500 !important;
            color: #64748B !important;
            background: #F8FAFC !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 999px !important;
            min-height: 22px !important;
            height: 22px !important;
            box-shadow: none !important;
            line-height: 1 !important;
        }
        [class*="st-key-cite_"] button:hover {
            background: #F1F5F9 !important;
            color: #0F6E56 !important;
            border-color: #9FD9C8 !important;
        }

        /* ── Agent text markdown headers — keep them in scale ───────────────
           Agent 2's diagnosis explanation often emits # / ## / ### markdown
           headers which Streamlit renders at h1/h2/h3 default sizes (way too
           large next to our section title). Cap them so they read as
           sub-headings, not page-spanning banners.

           IMPORTANT: scoped via `:not([style])` so the rule only matches
           headers that have NO inline style — i.e. the ones generated by
           plain `st.markdown("# header")` from agent text. The upload-screen
           hero ("Understand everything" / "the doctor just told you.") uses
           inline style="font-size:40px" and is correctly skipped. */
        section[data-testid="stMain"] [data-testid="stMarkdownContainer"] h1:not([style]) {
            font-size: 1.15rem !important;
            font-weight: 700 !important;
            margin: 14px 0 6px !important;
            color: #0A2A1F !important;
        }
        section[data-testid="stMain"] [data-testid="stMarkdownContainer"] h2:not([style]) {
            font-size: 1.02rem !important;
            font-weight: 700 !important;
            margin: 12px 0 4px !important;
            color: #0F6E56 !important;
        }
        section[data-testid="stMain"] [data-testid="stMarkdownContainer"] h3:not([style]) {
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            margin: 10px 0 4px !important;
            color: #1E293B !important;
        }
        section[data-testid="stMain"] [data-testid="stMarkdownContainer"] h4:not([style]) {
            font-size: 0.92rem !important;
            font-weight: 600 !important;
            margin: 8px 0 4px !important;
            color: #334155 !important;
        }

        /* ── Section title ───────────────────────────────────────────────────── */
        .diq-section-title {
            font-size: 1.18rem;
            font-weight: 800;
            color: #0A2A1F;
            letter-spacing: -0.01em;
            margin: 4px 0 12px;
            padding-bottom: 8px;
            position: relative;
        }
        .diq-section-title::after {
            content: '';
            position: absolute;
            bottom: 0; left: 0;
            width: 40px; height: 3px;
            background: linear-gradient(90deg, #0F6E56, #1D9E75);
            border-radius: 3px;
        }

        /* ── Medication card ─────────────────────────────────────────────────── */
        .diq-med-card {
            background: #ffffff;
            border-radius: 14px;
            border-left: 4px solid #6366F1;
            padding: 16px 20px;
            margin-bottom: 12px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.06);
            transition: box-shadow 0.2s ease, transform 0.15s ease;
        }
        .diq-med-card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.08), 0 8px 28px rgba(15,110,86,0.10);
            transform: translateY(-1px);
        }

        /* ── Appointment row ─────────────────────────────────────────────────── */
        .diq-appt-row {
            display: flex;
            align-items: flex-start;
            gap: 14px;
            padding: 14px 16px;
            background: #ffffff;
            border-radius: 12px;
            margin-bottom: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 2px 8px rgba(0,0,0,0.04);
            transition: box-shadow 0.2s ease;
        }
        .diq-appt-row:hover {
            box-shadow: 0 2px 8px rgba(0,0,0,0.08), 0 4px 16px rgba(15,110,86,0.08);
        }
        .diq-appt-dot {
            width: 10px; height: 10px;
            border-radius: 50%;
            background: linear-gradient(135deg, #0F6E56, #1D9E75);
            flex-shrink: 0;
            margin-top: 5px;
            box-shadow: 0 0 0 3px rgba(29,158,117,0.15);
        }

        /* ── Inline caregiver questions (embedded inside card, no extra chrome) ── */
        .diq-caregiver-questions-inline {
            background: #F0F9FF;
            border-left: 3px solid #0EA5E9;
            border-radius: 4px;
            padding: 8px 10px;
            margin-top: 10px;
        }
        .diq-caregiver-questions-inline ul {
            margin: 0;
            padding-left: 18px;
            font-size: 0.82rem;
            color: #0C4A6E;
        }
        .diq-caregiver-questions-inline li {
            margin-bottom: 3px;
            line-height: 1.35;
        }

        /* ── Recovery week cards ─────────────────────────────────────────────── */
        .diq-week-card {
            display: flex;
            align-items: center;
            gap: 12px;
            background: #ffffff;
            border-radius: 14px 14px 0 0;
            border-left: 4px solid #1D9E75;
            padding: 12px 18px 8px;
            margin-top: 14px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 4px 14px rgba(15,110,86,0.08);
        }
        .diq-week-badge {
            min-width: 36px;
            height: 36px;
            border-radius: 10px;
            background: linear-gradient(135deg, #0F6E56, #1D9E75);
            color: #fff;
            font-weight: 800;
            font-size: 0.78rem;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 6px rgba(15,110,86,0.25);
            flex-shrink: 0;
        }
        .diq-week-header {
            font-size: 1.0rem;
            font-weight: 700;
            color: #0A2A1F;
            letter-spacing: -0.01em;
        }
        .diq-week-body {
            background: #ffffff;
            border-radius: 0 0 14px 14px;
            border-left: 4px solid #1D9E75;
            padding: 4px 22px 14px 66px;
            margin-bottom: 12px;
            font-size: 0.9rem;
            line-height: 1.5;
            color: #1E293B;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 4px 14px rgba(15,110,86,0.08);
        }
        .diq-week-body p { margin: 0 0 0.4em; }
        .diq-week-body ul {
            margin: 4px 0 4px 0;
            padding-left: 0;
            list-style: none;
        }
        .diq-week-body li {
            margin-bottom: 6px;
            padding-left: 18px;
            position: relative;
        }
        .diq-week-body li::before {
            content: "";
            position: absolute;
            left: 4px;
            top: 0.5em;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #1D9E75;
            box-shadow: 0 0 0 2px rgba(29,158,117,0.18);
        }
        .diq-week-outro {
            background: linear-gradient(135deg, #F0FDF9, #E8F8F1);
            border: 1px solid rgba(29,158,117,0.25);
            border-radius: 14px;
            padding: 14px 20px;
            margin-top: 16px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03), 0 4px 14px rgba(15,110,86,0.06);
        }
        .diq-week-outro-label {
            font-size: 0.78rem;
            font-weight: 700;
            color: #0F6E56;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 4px;
        }
        .diq-week-outro-body {
            font-size: 0.9rem;
            line-height: 1.5;
            color: #0A2A1F;
        }
        .diq-week-outro-body ul {
            margin: 4px 0;
            padding-left: 0;
            list-style: none;
        }
        .diq-week-outro-body li {
            margin-bottom: 5px;
            padding-left: 18px;
            position: relative;
        }
        .diq-week-outro-body li::before {
            content: "";
            position: absolute;
            left: 4px;
            top: 0.5em;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #0F6E56;
            box-shadow: 0 0 0 2px rgba(15,110,86,0.18);
        }

        /* ── Warning card ────────────────────────────────────────────────────── */
        .diq-warning-card {
            background: linear-gradient(135deg, #FFF5F5, #FEF2F2);
            border-radius: 14px;
            border: 1px solid rgba(220,38,38,0.12);
            padding: 16px 20px;
            margin-bottom: 10px;
            box-shadow: 0 2px 8px rgba(220,38,38,0.06);
        }
        .diq-flag-row {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 7px 0;
        }
        .diq-flag-dot {
            width: 8px; height: 8px;
            border-radius: 50%;
            background: #DC2626;
            flex-shrink: 0;
            margin-top: 6px;
            box-shadow: 0 0 0 3px rgba(220,38,38,0.15);
        }

        /* ── Medication status badge ─────────────────────────────────────────── */
        .diq-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: #fff;
        }

        /* ── Changed banner ──────────────────────────────────────────────────── */
        .diq-changed-banner {
            background: linear-gradient(135deg, #FEF9C3, #FEF3C7);
            color: #92400E;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 0.72rem;
            font-weight: 600;
            margin-top: 6px;
            display: inline-block;
            border: 1px solid rgba(146,64,14,0.15);
        }

        /* ── Diagnosis "at a glance" block ───────────────────────────────────── */
        .diq-dx-label {
            font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.1em; color: #64748B; margin: 16px 0 8px;
        }
        .diq-dx-row {
            display: flex; align-items: center; gap: 12px;
            padding: 7px 0; font-size: 0.93rem; color: #1E293B; font-weight: 500;
        }
        .diq-dx-badge {
            display: inline-block;
            width: 4px; height: 20px;
            background: linear-gradient(180deg, #0F6E56, #1D9E75);
            border-radius: 3px;
            flex-shrink: 0;
        }
        .diq-dx-sep {
            border: none;
            border-top: 1px solid #E5E7EB;
            margin: 18px 0;
        }

        /* ── Citation chip (p.N) ─────────────────────────────────────────────── */
        div[data-testid="stButton"]:has(button[kind="secondary"]) {
            display: inline-flex !important;
            width: auto !important;
        }
        button[data-testid="baseButton-secondary"],
        button[kind="secondary"] {
            padding: 1px 6px !important;
            font-size: 0.6rem !important;
            font-weight: 600 !important;
            line-height: 1.4 !important;
            border-radius: 4px !important;
            background: rgba(15,110,86,0.06) !important;
            color: #0F6E56 !important;
            border: 1px solid rgba(15,110,86,0.2) !important;
            min-height: 0 !important;
            height: auto !important;
            box-shadow: none !important;
            transition: background 0.15s ease !important;
        }
        button[data-testid="baseButton-secondary"]:hover,
        button[kind="secondary"]:hover {
            background: rgba(15,110,86,0.12) !important;
            color: #0A5240 !important;
            border-color: rgba(15,110,86,0.35) !important;
            box-shadow: none !important;
        }

        /* ── Recovery section ────────────────────────────────────────────────── */
        .diq-recovery-col {
            font-size: 0.9rem; color: #334155; line-height: 1.9;
        }
        .diq-discharge-cond {
            background: linear-gradient(135deg, #F1F5F9, #EFF6FF);
            border-radius: 10px;
            padding: 10px 16px;
            font-size: 0.85rem;
            color: #475569;
            margin-top: 12px;
            border: 1px solid #E2E8F0;
        }

        /* ── Download button ─────────────────────────────────────────────────── */
        button[data-testid="baseButton-secondary"][kind="secondary"][data-testid*="download"],
        div[data-testid="stDownloadButton"] button {
            background: linear-gradient(135deg, #0F6E56, #1D9E75) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 0.82rem !important;
            padding: 8px 16px !important;
            box-shadow: 0 2px 8px rgba(15,110,86,0.25) !important;
            transition: opacity 0.2s ease !important;
        }
        div[data-testid="stDownloadButton"] button:hover {
            opacity: 0.9 !important;
            box-shadow: 0 4px 12px rgba(15,110,86,0.35) !important;
        }

        /* ── Hidden click-target buttons ─────────────────────────────────────── */
        div[data-testid="stElementContainer"]:has(.diq-hidden-btn-slot),
        div[data-testid="stElementContainer"]:has(.diq-hidden-btn-slot)
          + div[data-testid="stElementContainer"] {
            position: absolute !important;
            width: 1px !important;
            height: 1px !important;
            opacity: 0 !important;
            overflow: hidden !important;
            top: -9999px !important;
            left: -9999px !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        div[data-testid="stElementContainer"]:has(.diq-hidden-btn-slot)
          + div[data-testid="stElementContainer"] {
            pointer-events: auto !important;
        }

        /* ── Streamlit info/warning/error blocks ─────────────────────────────── */
        div[data-testid="stAlert"] {
            border-radius: 12px !important;
            border: none !important;
            font-size: 0.88rem !important;
        }

        /* ── Markdown prose inside results ───────────────────────────────────── */
        .stMarkdown p {
            font-size: 0.93rem;
            line-height: 1.75;
            color: #334155;
        }
        .stMarkdown li {
            font-size: 0.91rem;
            line-height: 1.7;
            color: #334155;
        }
        .stMarkdown h3 {
            font-size: 0.95rem !important;
            font-weight: 700 !important;
            color: #0A2A1F !important;
            margin: 14px 0 6px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


class _AnalyzeError(Exception):
    """
    Raised when /analyze returns a non-200 status so the upload handler
    can branch on the HTTP code (413 / 415 / 504 / 5xx) and show a
    user-friendly message for each case.
    """

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _call_analyze(pdf_bytes: bytes, filename: str, session_id: str | None = None) -> dict:
    """
    POST the uploaded PDF to the FastAPI /analyze endpoint.

    Args:
        pdf_bytes: Raw bytes of the uploaded file.
        filename:  Original filename for the multipart form field.
        session_id: Optional client-supplied session id. When provided, sent
            as the X-Discharge-Session-Id header so the backend records
            progress under this id and the loading UI can poll
            /progress/{session_id} during the long-running analyze call.

    Returns:
        Parsed PipelineResponse JSON dict.

    Raises:
        requests.exceptions.ConnectionError: If the backend is unreachable.
        requests.exceptions.Timeout:         If the server does not respond
            within the client-side timeout.
        _AnalyzeError: If the server returns a non-200 status. The HTTP code
            is preserved on the exception so the caller can show an error
            message tailored to the specific failure mode (413 for size,
            415 for wrong file type, 504 for pipeline timeout, 5xx generic).
    """
    headers = {"X-Discharge-Session-Id": session_id} if session_id else {}
    response = requests.post(
        _ANALYZE_URL,
        files={"file": (filename, pdf_bytes, "application/pdf")},
        headers=headers,
        timeout=180,
    )
    if response.status_code != 200:
        raise _AnalyzeError(
            status=response.status_code,
            message=response.text[:300],
        )
    return response.json()


def _format_date(iso_date: str | None) -> str:
    """
    Convert an ISO-format date string to "Month D, YYYY" display format.

    Falls back to the original string if parsing fails, so a relative phrase
    from the LLM ("in 7-10 days", "within 4 weeks") is shown verbatim rather
    than silently dropped.

    Args:
        iso_date: Date string, e.g. "2026-03-15", "in 7-10 days", or None.

    Returns:
        str: Human-readable date, e.g. "March 15, 2026", the original phrase
             when not ISO-parseable, or "Date not specified" when None/empty.
    """
    if not iso_date:
        return "Date not specified"
    try:
        from datetime import datetime
        dt = datetime.strptime(iso_date.strip(), "%Y-%m-%d")
        return dt.strftime("%B %-d, %Y")
    except ValueError:
        return iso_date.strip()


def _date_is_iso(value: str | None) -> bool:
    """True iff `value` looks like a YYYY-MM-DD ISO date the renderer can
    format with a calendar icon. Relative phrases like 'in 7-10 days' or
    'within 4 weeks' return False so the renderer can pick a clock icon
    instead, signalling 'timing, not a fixed date'."""
    if not value:
        return False
    try:
        from datetime import datetime
        datetime.strptime(value.strip(), "%Y-%m-%d")
        return True
    except (ValueError, AttributeError):
        return False


def _strip_html_tags(text: str) -> str:
    """
    Remove all HTML tags from a string and return clean plain text.

    Args:
        text: Input string that may contain HTML tags.

    Returns:
        str: Plain text with all HTML tags stripped and whitespace trimmed.
    """
    return re.sub(r"<[^>]+>", "", text).strip()


def _simple_md_to_html(text: str) -> str:
    """
    Convert a small subset of markdown (paragraphs, bullets, **bold**) to
    inline HTML so we can embed agent text inside an HTML container that
    Streamlit renders in a single st.markdown call.

    Why this exists: Streamlit emits each `st.markdown(..., unsafe_allow_html=True)`
    call into its own `[data-testid="stMarkdownContainer"]` div. That means an
    open `<details>` or `<div>` tag in one call CANNOT contain content
    rendered by a later call - the orphan content leaks below the closed
    container. To put markdown-formatted agent text inside a styled card,
    we have to convert the markdown to HTML ourselves and inline it inside
    the wrapper, so the whole thing fits in one st.markdown call.

    Supported syntax:
      - Lines beginning with "- " or "* " - rendered as <li> inside a <ul>.
      - Blank line - paragraph break (closes the current <p> and any open list).
      - Inline **bold** - wrapped in <strong>.
      - Anything else - joined into a <p> paragraph.

    Args:
        text: Plain markdown text from an agent (recovery body, rationale).

    Returns:
        str: Inline HTML safe to embed inside another HTML block.
    """
    if not text:
        return ""

    # Escape HTML special characters first; the markdown patterns we care
    # about (-, *, **) are not affected by html.escape().
    escaped = html.escape(text)

    lines = escaped.strip().split("\n")
    html_parts: list[str] = []
    para_lines: list[str] = []
    in_list = False

    def flush_paragraph() -> None:
        if para_lines:
            joined = " ".join(line.strip() for line in para_lines).strip()
            if joined:
                html_parts.append(f"<p>{joined}</p>")
            para_lines.clear()

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    def open_list() -> None:
        nonlocal in_list
        if not in_list:
            html_parts.append("<ul>")
            in_list = True

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            close_list()
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            flush_paragraph()
            open_list()
            item = stripped[2:].strip()
            html_parts.append(f"<li>{item}</li>")
            continue
        # Non-list, non-blank line: starts or continues a paragraph.
        close_list()
        para_lines.append(stripped)

    flush_paragraph()
    close_list()

    out = "".join(html_parts)
    # Inline **bold** -> <strong>. Run after escaping so any literal asterisks
    # in the source text would have stayed as plain "*" (not part of an
    # escape sequence) and still match this pattern.
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    return out


def _strip_em_dashes(text: str) -> str:
    """
    Replace em dashes (—) and en dashes (–) with simple hyphens so the UI
    never shows them. Per project preference, em dashes are not used
    anywhere in user-facing text.

    The mapping deliberately preserves dash structure (em dash → hyphen
    with surrounding spaces) rather than collapsing to a comma. This
    keeps the Agent 3 medication parser's " - stopping:" marker matchable
    after sanitization, and reads naturally in prose. Runs on every
    LLM-sourced string before it reaches the DOM.
    """
    if not text:
        return text
    out = text.replace(" — ", " - ")
    out = out.replace(" —", " -")
    out = out.replace("— ", "- ")
    out = out.replace("—", "-")
    # En dash: replace with hyphen for things like number ranges.
    out = out.replace("–", "-")
    return out


def _clean_str(value: object) -> str:
    """
    Coerce any value to a plain-text string with HTML tags stripped.

    Applied to every LLM-sourced string before it is embedded inside a
    Streamlit unsafe_allow_html=True markdown block so that stray HTML
    markup in the model output cannot break layout or render as visible
    tag text. Also strips em/en dashes so the UI never shows them
    regardless of whether the LLM honored the prompt-level instruction.
    None, empty strings, and non-string values all return "".

    Args:
        value: Any value from an extraction / agent dict.

    Returns:
        str: Stripped plain-text representation, or "" if falsy.
    """
    if value is None or value == "":
        return ""
    return _strip_em_dashes(_strip_html_tags(str(value)))


def _empty_generation_message(result: dict, section_label: str) -> None:
    """
    When an agent section is blank, explain partial pipeline / config issues
    instead of a bare caption — especially during provider outages or 429s.
    """
    status = (result.get("pipeline_status") or "").lower()
    if status == "partial":
        st.warning(
            f"{section_label} could not be generated. "
            "The AI service may be busy, rate-limited, or misconfigured "
            "(check .env API keys). This is not medical advice. Contact your "
            "care team or emergency services for urgent symptoms."
        )
    else:
        st.caption(f"{section_label} is not available for this document.")


def _pdf_safe_txt(text: str) -> str:
    """FPDF core fonts are latin-1; replace unsupported characters."""
    if not text:
        return ""
    return text.encode("latin-1", "replace").decode("latin-1")


def _build_summary_pdf_bytes(result: dict) -> bytes:
    """
    Build a simple take-home PDF from the current pipeline result (post-demo).

    Uses fpdf2 (already in requirements.txt). Not a clinical record — patient
    education summary only.
    """
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)

    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, txt=_pdf_safe_txt("DischargeIQ: Plain-language summary"))
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(
        0,
        4,
        txt=_pdf_safe_txt(
            "AI-generated for education only. Not medical advice. "
            "Confirm all instructions and warning signs with your care team "
            "before relying on this document."
        ),
    )
    pdf.ln(3)

    ext = result.get("extraction") or {}
    patient = _clean_str(ext.get("patient_name")) or "Patient"
    ddate = _clean_str(ext.get("discharge_date"))
    pdf.multi_cell(0, 5, txt=_pdf_safe_txt(f"Patient: {patient}"))
    if ddate:
        pdf.multi_cell(0, 5, txt=_pdf_safe_txt(f"Discharge date: {ddate}"))
    pdf.ln(2)

    def add_section(title: str, body: str) -> None:
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(0, 6, txt=_pdf_safe_txt(title))
        pdf.set_font("Helvetica", "", 10)
        content = body.strip() if body.strip() else "(Not generated.)"
        pdf.multi_cell(0, 5, txt=_pdf_safe_txt(content))
        pdf.ln(2)

    add_section(
        "1. What happened to you",
        _clean_str(result.get("diagnosis_explanation", "")),
    )
    add_section(
        "2. Your medications explained",
        _clean_str(result.get("medication_rationale", "")),
    )
    add_section(
        "3. Your recovery timeline",
        _clean_str(result.get("recovery_trajectory", "")),
    )
    add_section(
        "4. Warning signs: when to get help",
        _clean_str(result.get("escalation_guide", "")),
    )

    dx = _clean_str(ext.get("primary_diagnosis", ""))
    meds = ext.get("medications") or []
    med_lines = []
    for m in meds:
        if isinstance(m, dict):
            nm = _clean_str(m.get("name"))
            if nm:
                med_lines.append(nm)
    detail_lines = [f"Primary diagnosis: {dx}"] if dx else []
    if med_lines:
        detail_lines.append("Medications noted: " + ", ".join(med_lines))
    add_section(
        "5. Discharge details (from your document)",
        "\n".join(detail_lines) if detail_lines else "",
    )

    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1", "replace")
    return bytes(out)


def _hidden_click_target(label: str, key: str) -> bool:
    """
    Render a Streamlit button preceded by a diq-hidden-btn-slot marker.

    CSS in _inject_global_css() collapses both the marker container and
    the button container to an invisible 1px dot. The button remains in
    the DOM and is programmatically clickable from parent-DOM JS via
    `button.click()` — React's synthetic-event system picks that up and
    fires the normal onClick handler.

    Args:
        label: Unique sentinel text used as both button label and JS lookup key.
        key:   Streamlit widget key (must be unique across the page).

    Returns:
        bool: True if the button was just clicked in this run.
    """
    st.markdown(
        f'<span class="diq-hidden-btn-slot" data-diq-slot="{label}"></span>',
        unsafe_allow_html=True,
    )
    return st.button(label, key=key)


def _citation_button(page: int, source_text: str, key_suffix: str) -> bool:
    """
    Render a small subtle citation chip labelled "Page N" that opens the
    source PDF modal at the cited page on click.

    Label changed from the cryptic "p.N" to "Page N" so first-time users
    understand it's a page reference. Streamlit puts the widget key on the
    container as a CSS class (e.g. `st-key-cite_med_0`); the global CSS
    rule `[class*="st-key-cite_"] button` picks up these buttons specifically
    and applies subtle chip styling without affecting other Streamlit
    buttons. No marker element is injected, so column layouts stay intact.

    Args:
        page:        1-indexed page number from the source span.
        source_text: Verbatim quote stored on the pending citation.
        key_suffix:  Unique string suffix for the Streamlit widget key.

    Returns:
        bool: True if the button was clicked in this run.
    """
    clicked = st.button(
        f"Page {page}",
        key=f"cite_{key_suffix}",
        type="secondary",
    )
    if clicked:
        st.session_state[_S_PENDING_CITATION] = {
            "page": page,
            "text": source_text,
        }
        st.rerun()
    return clicked


def _reset_session() -> None:
    """Clear result + PDF state to return to the upload screen."""
    st.session_state[_S_RESULT] = None
    st.session_state[_S_PDF_BYTES] = None
    st.session_state[_S_PDF_SESSION_ID] = None
    st.session_state[_S_FILE_NAME] = "document.pdf"
    st.session_state[_S_ACTIVE_TAB] = "diagnosis"
    st.session_state[_S_PENDING_CITATION] = None
    st.session_state[_S_STAGED_PDF_BYTES] = None
    st.session_state[_S_STAGED_PDF_NAME] = "document.pdf"
    st.session_state[_S_UPLOAD_ERROR] = None
    # Bump the file_uploader's key suffix so the widget remounts empty —
    # otherwise the old upload would re-stage on the next render and the
    # zone would jump straight to "Ready to analyze" instead of a clean
    # upload prompt.
    st.session_state["_diq_uploader_counter"] = (
        st.session_state.get("_diq_uploader_counter", 0) + 1
    )


# ── Parent-DOM cleanup (used when returning to upload screen) ────────────────

def _cleanup_parent_dom() -> None:
    """
    Strip every DischargeIQ-injected element from window.parent.document.

    Invoked from _render_upload_screen so that when the user clicks
    "Upload new" we don't leave a stale header, tab bar, chat panel, or
    PDF modal behind from the previous summary view.
    """
    ids_json = json.dumps(_DIQ_PARENT_DOM_IDS)
    cleanup_html = f"""<!DOCTYPE html><html><head><script>
(function() {{
  var pdoc = window.parent.document;
  var ids = {ids_json};
  ids.forEach(function(id) {{
    var el = pdoc.getElementById(id);
    if (el) el.remove();
  }});
  var main = pdoc.querySelector('section[data-testid="stMain"]');
  if (main) main.style.paddingRight = '';
}})();
</script></head><body></body></html>"""
    st.components.v1.html(cleanup_html, height=1, scrolling=False)


def _clear_browser_session_on_fresh_load() -> None:
    """
    One-shot cleanup that runs once per Streamlit server session.

    On browser refresh Streamlit resets st.session_state, but the
    browser-side window.parent.sessionStorage (chat history, chat
    width, minimized flag) and any leftover injected DOM nodes survive
    the refresh. This helper wipes both so the app always boots from a
    clean slate after Cmd-R.

    Gated by st.session_state[_S_BOOTSTRAPPED]: runs once, then flips
    the flag so subsequent reruns within the same session do NOT wipe
    user resize/minimize preferences.
    """
    if st.session_state.get(_S_BOOTSTRAPPED):
        return

    ids_json = json.dumps(_DIQ_PARENT_DOM_IDS)
    bootstrap_html = f"""<!DOCTYPE html><html><head><script>
(function() {{
  var pdoc = window.parent.document;
  try {{
    var ss = window.parent.sessionStorage;
    // Remove every diq_-prefixed key so chat thread, width, and
    // minimized flag all reset on page refresh.
    var stale = [];
    for (var i = 0; i < ss.length; i++) {{
      var k = ss.key(i);
      if (k && k.indexOf('diq_') === 0) stale.push(k);
    }}
    stale.forEach(function(k) {{ ss.removeItem(k); }});
  }} catch(e) {{}}
  var ids = {ids_json};
  ids.forEach(function(id) {{
    var el = pdoc.getElementById(id);
    if (el) el.remove();
  }});
  var main = pdoc.querySelector('section[data-testid="stMain"]');
  if (main) main.style.paddingRight = '';
}})();
</script></head><body></body></html>"""
    st.components.v1.html(bootstrap_html, height=1, scrolling=False)
    st.session_state[_S_BOOTSTRAPPED] = True


# ── App header (teal sticky bar) ─────────────────────────────────────────────

def _render_app_header(result: dict) -> None:
    """
    Inject the teal sticky app header into window.parent.document.body.

    Layout:
      Left  — "DischargeIQ" wordmark (15px white, weight 700).
      Right — patient name, discharge date, verified/partial pill,
              "View original document" text link, "Upload new" ghost button.

    All visible buttons in the injected header forward their clicks to
    hidden Streamlit buttons (rendered by _hidden_click_target below),
    so session state mutations still flow through Streamlit's normal
    rerun cycle.

    Args:
        result: PipelineResponse dict returned by /analyze.
    """
    ext = result.get("extraction", {})
    name = _clean_str(ext.get("patient_name")) or "Patient"
    date_raw = ext.get("discharge_date")
    date_display = _clean_str(_format_date(date_raw))
    pipeline_status = result.get("pipeline_status", "partial")
    advisory_warnings = result.get("extraction_warnings", []) or []

    # Three-tier status pill:
    #   complete               → green "Verified"
    #   complete_with_warnings → grey "Verified*" with advisory tooltip
    #   partial  (or anything) → amber "Incomplete"
    pill_title = ""
    if pipeline_status == "complete":
        pill_bg = "transparent"
        pill_border = "rgba(255,255,255,0.8)"
        pill_fg = "#ffffff"
        pill_text = "Verified"
    elif pipeline_status == "complete_with_warnings":
        pill_bg = "rgba(255,255,255,0.15)"
        pill_border = "rgba(255,255,255,0.5)"
        pill_fg = "#ffffff"
        pill_text = "Verified*"
        # Native tooltip — shows the list of advisory gaps when the user
        # hovers the pill so they know what is missing without cluttering
        # the bar.
        if advisory_warnings:
            pill_title = "Some non-critical fields missing: " + "; ".join(
                advisory_warnings
            )
    else:
        pill_bg = "#FCD34D"
        pill_border = "transparent"
        pill_fg = "#713F12"
        pill_text = "Incomplete"

    # Sentinel labels used as both button text and JS lookup key.
    upload_sentinel   = "__diq_upload_new_hidden__"
    view_pdf_sentinel = "__diq_view_pdf_hidden__"
    tour_sentinel     = "__diq_replay_tour__"

    # Hidden click-target buttons. These own the state changes.
    if _hidden_click_target(upload_sentinel, key="upload_new"):
        _reset_session()
        st.rerun()

    if _hidden_click_target(view_pdf_sentinel, key="view_pdf_link"):
        st.session_state[_S_PENDING_CITATION] = {"page": 1, "text": ""}
        st.rerun()

    if _hidden_click_target(tour_sentinel, key="replay_tour"):
        # Set a one-shot flag the tour injector reads on the next rerun. Doing
        # the cleanup inside the same iframe that injects the tour avoids the
        # race we used to have when two iframes (cleanup + tour) loaded in an
        # undefined order.
        st.session_state[_S_TOUR_REPLAY] = True
        st.rerun()

    header_css = """
      #diq-app-header {
        position: sticky; top: 0; z-index: 600;
        width: 100%; background: #0f6e56;
        height: 56px; padding: 0 20px;
        display: flex; align-items: center;
        box-sizing: border-box;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      }
      #diq-app-header .diq-brand {
        color: #ffffff; font-size: 15px; font-weight: 700;
        flex: 1;
      }
      #diq-app-header .diq-header-right {
        display: flex; align-items: center; gap: 14px;
      }
      #diq-app-header .diq-patient-name {
        color: #ffffff; font-size: 13px; font-weight: 700;
        white-space: nowrap;
      }
      #diq-app-header .diq-patient-date {
        color: #9fe1cb; font-size: 11px;
        white-space: nowrap;
      }
      #diq-app-header .diq-pill {
        padding: 2px 10px; border-radius: 10px;
        font-size: 11px; font-weight: 600;
        white-space: nowrap;
      }
      #diq-app-header .diq-view-pdf {
        color: #9fe1cb; font-size: 11px;
        text-decoration: underline; cursor: pointer;
        background: none; border: none; padding: 0;
        font-family: inherit;
      }
      #diq-app-header .diq-view-pdf:hover { color: #ffffff; }
      #diq-app-header .diq-upload-btn {
        border: 1px solid rgba(255,255,255,0.4);
        color: #ffffff; background: transparent;
        padding: 4px 12px; border-radius: 6px;
        font-size: 11px; cursor: pointer;
        font-family: inherit;
      }
      #diq-app-header .diq-upload-btn:hover {
        background: rgba(255,255,255,0.1);
      }
    """

    inner_html = f"""
      <div class="diq-brand">DischargeIQ</div>
      <div class="diq-header-right">
        <span class="diq-patient-name">{name}</span>
        <span class="diq-patient-date">Discharged {date_display}</span>
        <span class="diq-pill"
              title="{pill_title}"
              style="background:{pill_bg};color:{pill_fg};
                     border:1px solid {pill_border};">
          {pill_text}
        </span>
        <button id="diq-view-pdf-btn" class="diq-view-pdf" type="button">
          View original document
        </button>
        <button id="diq-tour-btn" class="diq-upload-btn" type="button">
          Take tour
        </button>
        <button id="diq-upload-new-btn" class="diq-upload-btn" type="button">
          Upload new
        </button>
      </div>
    """

    header_html = f"""<!DOCTYPE html><html><head><script>
(function() {{
  var pdoc = window.parent.document;

  ['diq-app-header', 'diq-app-header-styles'].forEach(function(id) {{
    var el = pdoc.getElementById(id);
    if (el) el.remove();
  }});

  var style = pdoc.createElement('style');
  style.id = 'diq-app-header-styles';
  style.textContent = {json.dumps(header_css)};
  pdoc.head.appendChild(style);

  var bar = pdoc.createElement('div');
  bar.id = 'diq-app-header';
  bar.innerHTML = {json.dumps(inner_html)};
  pdoc.body.insertBefore(bar, pdoc.body.firstChild);

  // Forward a click from a parent-DOM button to the hidden Streamlit button
  // identified by `label`.  Streamlit may not have rendered the marker span
  // yet (rerun in flight, container not mounted), so we poll up to 20 times
  // at 50ms intervals = 1s budget.  This is well above the typical Streamlit
  // mount latency (50-150ms) but still feels instant to a user.
  function clickHiddenBtn(label, retriesLeft) {{
    if (retriesLeft === undefined) retriesLeft = 20;
    var marker = pdoc.querySelector(
      'span[data-diq-slot="' + label + '"]'
    );
    if (!marker) {{
      if (retriesLeft > 0) {{
        setTimeout(function() {{ clickHiddenBtn(label, retriesLeft - 1); }}, 50);
      }} else {{
        console.warn('[diq] hidden button slot not found after retries:', label);
      }}
      return;
    }}
    var markerContainer = marker.closest(
      'div[data-testid="stElementContainer"]'
    );
    if (!markerContainer) {{
      if (retriesLeft > 0) {{
        setTimeout(function() {{ clickHiddenBtn(label, retriesLeft - 1); }}, 50);
      }} else {{
        console.warn('[diq] marker container not found after retries:', label);
      }}
      return;
    }}
    var btnContainer = markerContainer.nextElementSibling;
    if (!btnContainer) {{
      if (retriesLeft > 0) {{
        setTimeout(function() {{ clickHiddenBtn(label, retriesLeft - 1); }}, 50);
      }} else {{
        console.warn('[diq] hidden button sibling not found after retries:', label);
      }}
      return;
    }}
    var btn = btnContainer.querySelector('button');
    if (btn) {{
      console.log('[diq] forwarding click to hidden button:', label);
      // Belt-and-suspenders: .click() works for plain DOM buttons, but some
      // React-controlled buttons only respond to a dispatched MouseEvent.
      // Fire both so either path triggers Streamlit's onClick handler.
      btn.click();
      try {{
        btn.dispatchEvent(new MouseEvent('click', {{
          bubbles: true, cancelable: true, view: window
        }}));
      }} catch(e) {{ /* MouseEvent unsupported in very old browsers */ }}
    }} else if (retriesLeft > 0) {{
      setTimeout(function() {{ clickHiddenBtn(label, retriesLeft - 1); }}, 50);
    }} else {{
      console.warn('[diq] hidden button element not found after retries:', label);
    }}
  }}

  var upBtn = pdoc.getElementById('diq-upload-new-btn');
  if (upBtn) upBtn.addEventListener('click', function() {{
    clickHiddenBtn({json.dumps(upload_sentinel)});
  }});

  var viewBtn = pdoc.getElementById('diq-view-pdf-btn');
  if (viewBtn) viewBtn.addEventListener('click', function() {{
    clickHiddenBtn({json.dumps(view_pdf_sentinel)});
  }});

  var tourBtn = pdoc.getElementById('diq-tour-btn');
  if (tourBtn) tourBtn.addEventListener('click', function() {{
    clickHiddenBtn({json.dumps(tour_sentinel)});
  }});

  // Logo click navigates to the "What Happened" tab by reusing the tab
  // bar's hidden sentinel button — no extra Python button needed.
  var brandEl = pdoc.querySelector('#diq-app-header .diq-brand');
  if (brandEl) {{
    brandEl.style.cursor = 'pointer';
    brandEl.addEventListener('click', function() {{
      clickHiddenBtn('__diq_tab_diagnosis__');
    }});
  }}
}})();
</script></head><body></body></html>"""

    st.components.v1.html(header_html, height=1, scrolling=False)

    # Extraction warnings are rendered below the injected header so the patient
    # still sees them. "Not a discharge summary" gets elevated styling.
    for warning in result.get("extraction_warnings", []):
        if "may not be a hospital discharge summary" in warning.lower():
            st.error(warning)
        else:
            st.info(warning)


# ── Tab bar ──────────────────────────────────────────────────────────────────

def _render_tab_bar(active_tab: str) -> None:
    """
    Inject a horizontal tab bar directly below the app header.

    Each tab is rendered as a custom <button> inside the injected HTML,
    styled via scoped CSS. Clicks are forwarded to per-tab hidden
    Streamlit buttons that own the active-tab state transition.

    Args:
        active_tab: Key of the currently active tab. Determines which
                    tab pill gets the .active modifier class.
    """
    # Hidden click-target buttons — one per tab. Each sentinel encodes
    # the tab key so JS can forward clicks by constructing the label
    # string at click time.
    for tab_key, _tab_label in _TABS:
        sentinel = f"__diq_tab_{tab_key}__"
        if _hidden_click_target(sentinel, key=f"tab_btn_{tab_key}"):
            st.session_state[_S_ACTIVE_TAB] = tab_key
            st.session_state[_S_PENDING_CITATION] = None
            st.rerun()

    tab_css = """
      #diq-tab-bar {
        position: sticky; top: 56px; z-index: 599;
        background: #ffffff;
        border-bottom: 1px solid #e2e8f0;
        display: flex; padding: 0 20px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      }
      #diq-tab-bar .diq-tab {
        background: transparent; border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0;
        padding: 10px 16px; font-size: 13px;
        color: #64748b; cursor: pointer;
        font-family: inherit;
        transition: color 0.15s, border-color 0.15s;
      }
      #diq-tab-bar .diq-tab:hover { color: #0f6e56; }
      #diq-tab-bar .diq-tab.active {
        color: #0f6e56;
        border-bottom-color: #0f6e56;
        font-weight: 500;
      }
    """

    tab_items_html = "".join(
        f'<button id="diq-tab-{k}" class="diq-tab{" active" if k == active_tab else ""}" '
        f'data-tab-key="{k}" type="button">{label}</button>'
        for k, label in _TABS
    )

    tab_html = f"""<!DOCTYPE html><html><head><script>
(function() {{
  var pdoc = window.parent.document;

  ['diq-tab-bar', 'diq-tab-bar-styles'].forEach(function(id) {{
    var el = pdoc.getElementById(id);
    if (el) el.remove();
  }});

  var style = pdoc.createElement('style');
  style.id = 'diq-tab-bar-styles';
  style.textContent = {json.dumps(tab_css)};
  pdoc.head.appendChild(style);

  var bar = pdoc.createElement('div');
  bar.id = 'diq-tab-bar';
  bar.innerHTML = {json.dumps(tab_items_html)};

  // Insert the tab bar immediately after the app header so it sticks
  // just below it. Fall back to body append if header isn't mounted yet.
  var header = pdoc.getElementById('diq-app-header');
  if (header && header.parentNode) {{
    header.parentNode.insertBefore(bar, header.nextSibling);
  }} else {{
    pdoc.body.appendChild(bar);
  }}

  // Forward a click from a parent-DOM button to the hidden Streamlit button
  // identified by `label`.  Streamlit may not have rendered the marker span
  // yet (rerun in flight, container not mounted), so we poll up to 20 times
  // at 50ms intervals = 1s budget.  This is well above the typical Streamlit
  // mount latency (50-150ms) but still feels instant to a user.
  function clickHiddenBtn(label, retriesLeft) {{
    if (retriesLeft === undefined) retriesLeft = 20;
    var marker = pdoc.querySelector(
      'span[data-diq-slot="' + label + '"]'
    );
    if (!marker) {{
      if (retriesLeft > 0) {{
        setTimeout(function() {{ clickHiddenBtn(label, retriesLeft - 1); }}, 50);
      }} else {{
        console.warn('[diq] hidden button slot not found after retries:', label);
      }}
      return;
    }}
    var markerContainer = marker.closest(
      'div[data-testid="stElementContainer"]'
    );
    if (!markerContainer) {{
      if (retriesLeft > 0) {{
        setTimeout(function() {{ clickHiddenBtn(label, retriesLeft - 1); }}, 50);
      }} else {{
        console.warn('[diq] marker container not found after retries:', label);
      }}
      return;
    }}
    var btnContainer = markerContainer.nextElementSibling;
    if (!btnContainer) {{
      if (retriesLeft > 0) {{
        setTimeout(function() {{ clickHiddenBtn(label, retriesLeft - 1); }}, 50);
      }} else {{
        console.warn('[diq] hidden button sibling not found after retries:', label);
      }}
      return;
    }}
    var btn = btnContainer.querySelector('button');
    if (btn) {{
      console.log('[diq] forwarding click to hidden button:', label);
      // Belt-and-suspenders: .click() works for plain DOM buttons, but some
      // React-controlled buttons only respond to a dispatched MouseEvent.
      // Fire both so either path triggers Streamlit's onClick handler.
      btn.click();
      try {{
        btn.dispatchEvent(new MouseEvent('click', {{
          bubbles: true, cancelable: true, view: window
        }}));
      }} catch(e) {{ /* MouseEvent unsupported in very old browsers */ }}
    }} else if (retriesLeft > 0) {{
      setTimeout(function() {{ clickHiddenBtn(label, retriesLeft - 1); }}, 50);
    }} else {{
      console.warn('[diq] hidden button element not found after retries:', label);
    }}
  }}

  bar.querySelectorAll('.diq-tab').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      clickHiddenBtn('__diq_tab_' + btn.dataset.tabKey + '__');
    }});
  }});
}})();
</script></head><body></body></html>"""

    st.components.v1.html(tab_html, height=1, scrolling=False)


# ── PDF modal overlay ────────────────────────────────────────────────────────

# In-browser embedding cap — keeps the injected HTML component reasonable;
# above this size we fall back to GET /pdf/{id} only (needs a warm backend).
_MAX_PDF_EMBED_BYTES = 4 * 1024 * 1024


def _inject_pdf_modal(
    pdf_session_id: str | None,
    page: int,
    pdf_bytes: bytes | None = None,
) -> None:
    """
    Inject a full-screen PDF modal into window.parent.document.body.

    Called one-shot by _render_summary_screen when _S_PENDING_CITATION
    is set (either by a [p.N] chip click or the header "View original
    document" link). The pending state is consumed after this call so
    the modal does not re-inject on subsequent reruns.

    When upload bytes are still in session state, the PDF is shown from a
    browser blob URL so "View original document" still works after a backend
    restart (uvicorn --reload clears the in-memory PDF store).

    Args:
        pdf_session_id: UUID from the /analyze response for GET /pdf/{id}.
        page:           1-indexed page number to open the PDF at.
        pdf_bytes:      Optional raw PDF from the upload; preferred for display.
    """
    raw = pdf_bytes
    if raw is not None and isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw)
    else:
        raw = None

    embed_b64: str | None = None
    if raw is not None and len(raw) <= _MAX_PDF_EMBED_BYTES:
        embed_b64 = base64.b64encode(raw).decode("ascii")

    if not pdf_session_id and not embed_b64:
        st.warning("PDF not available for this session. Please re-upload the document.")
        return

    iframe_src = f"{_API_BASE}/pdf/{pdf_session_id}#page={page}" if pdf_session_id else ""
    iframe_src_attr = "about:blank" if embed_b64 else iframe_src

    modal_css = """
      #diq-pdf-modal-overlay {
        position: fixed; inset: 0;
        background: rgba(0, 0, 0, 0.5);
        /* Must sit above the chat panel (#diq-chat-panel, z-index 9999)
           and floating bubble so the PDF modal is always the foreground
           surface when it's open. */
        z-index: 10500;
        display: flex; align-items: center; justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      }
      #diq-pdf-modal-box {
        width: 80vw; height: 85vh;
        background: #ffffff;
        border-radius: 12px;
        overflow: hidden;
        display: flex; flex-direction: column;
        box-shadow: 0 10px 40px rgba(0,0,0,0.25);
      }
      #diq-pdf-modal-header {
        display: flex; align-items: center;
        height: 44px; padding: 0 16px;
        border-bottom: 1px solid #e2e8f0;
        flex-shrink: 0;
      }
      #diq-pdf-modal-header .diq-mh-left {
        flex: 1; font-weight: 700; font-size: 14px; color: #1E293B;
      }
      #diq-pdf-modal-header .diq-mh-center {
        flex: 1; text-align: center; font-size: 13px; color: #64748B;
      }
      #diq-pdf-modal-header .diq-mh-right {
        flex: 1; text-align: right;
      }
      #diq-pdf-modal-close {
        background: transparent; border: none;
        font-size: 20px; cursor: pointer; color: #64748B;
        padding: 0 6px; line-height: 1;
      }
      #diq-pdf-modal-close:hover { color: #1E293B; }
      #diq-pdf-modal-iframe {
        flex: 1; width: 100%;
        border: none; display: block;
      }
    """

    modal_body_html = f"""
      <div id="diq-pdf-modal-overlay">
        <div id="diq-pdf-modal-box">
          <div id="diq-pdf-modal-header">
            <div class="diq-mh-left">Original document</div>
            <div class="diq-mh-center">Page {page}</div>
            <div class="diq-mh-right">
              <button id="diq-pdf-modal-close" type="button"
                      aria-label="Close">&#10005;</button>
            </div>
          </div>
          <iframe id="diq-pdf-modal-iframe" src="{iframe_src_attr}"></iframe>
        </div>
      </div>
    """

    b64_literal = json.dumps(embed_b64)
    server_url_literal = json.dumps(iframe_src)

    # Streamlit short-circuits st.components.v1.html when the HTML body matches
    # the previous call at the same script position — the iframe is reused and
    # the injection script does NOT re-run, so opening the modal a second time
    # would silently do nothing. Bump and embed a per-open nonce as an HTML
    # comment so every call produces unique bytes and Streamlit forces a fresh
    # iframe (and the cleanup-then-inject script re-runs).
    st.session_state[_S_PDF_MODAL_NONCE] = (
        st.session_state.get(_S_PDF_MODAL_NONCE, 0) + 1
    )
    nonce = st.session_state[_S_PDF_MODAL_NONCE]

    injection_html = f"""<!DOCTYPE html><html><head>
<!-- diq-pdf-modal nonce={nonce} -->
<script>
(function() {{
  var pdoc = window.parent.document;
  var embeddedB64 = {b64_literal};
  var serverPdfUrl = {server_url_literal};
  var blobUrl = null;

  // Idempotent: strip any previous modal + styles before re-injecting.
  ['diq-pdf-modal', 'diq-pdf-modal-styles'].forEach(function(id) {{
    var el = pdoc.getElementById(id);
    if (el) el.remove();
  }});

  var style = pdoc.createElement('style');
  style.id = 'diq-pdf-modal-styles';
  style.textContent = {json.dumps(modal_css)};
  pdoc.head.appendChild(style);

  var root = pdoc.createElement('div');
  root.id = 'diq-pdf-modal';
  root.innerHTML = {json.dumps(modal_body_html)};
  pdoc.body.appendChild(root);

  var iframe = pdoc.getElementById('diq-pdf-modal-iframe');
  if (iframe && embeddedB64 && embeddedB64.length > 0) {{
    try {{
      var bin = atob(embeddedB64);
      var arr = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
      var blob = new Blob([arr], {{ type: 'application/pdf' }});
      blobUrl = URL.createObjectURL(blob);
      iframe.src = blobUrl + '#page=' + {int(page)};
    }} catch (e) {{
      if (serverPdfUrl) iframe.src = serverPdfUrl;
    }}
  }} else if (iframe && serverPdfUrl && iframe.getAttribute('src') === 'about:blank') {{
    iframe.src = serverPdfUrl;
  }}

  function onKeydown(evt) {{
    if (evt.key === 'Escape') closeModal();
  }}

  function closeModal() {{
    if (blobUrl) {{
      try {{ URL.revokeObjectURL(blobUrl); }} catch (e) {{}}
      blobUrl = null;
    }}
    pdoc.removeEventListener('keydown', onKeydown);
    var m = pdoc.getElementById('diq-pdf-modal');
    var s = pdoc.getElementById('diq-pdf-modal-styles');
    if (m) m.remove();
    if (s) s.remove();
  }}

  var overlay = pdoc.getElementById('diq-pdf-modal-overlay');
  if (overlay) {{
    overlay.addEventListener('click', function(evt) {{
      // Close only when clicking the dim background, not the modal box.
      if (evt.target === overlay) closeModal();
    }});
  }}
  var closeBtn = pdoc.getElementById('diq-pdf-modal-close');
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  // ESC closes the modal — listener is attached to the parent document so it
  // fires regardless of which iframe currently has focus, and torn down by
  // closeModal() to prevent leaks across re-opens.
  pdoc.addEventListener('keydown', onKeydown);
}})();
</script></head><body></body></html>"""

    st.components.v1.html(injection_html, height=1, scrolling=False)


# ── Section: Diagnosis ───────────────────────────────────────────────────────

def _render_section_diagnosis(result: dict) -> None:
    """
    Render the diagnosis tab: explanation paragraph, citation chip, FK
    score, and pill-style secondary diagnoses.

    Args:
        result: PipelineResponse dict.
    """
    ext = result.get("extraction", {})
    explanation = _strip_em_dashes((result.get("diagnosis_explanation") or "").strip())
    source = ext.get("primary_diagnosis_source")
    secondary = ext.get("secondary_diagnoses", [])

    st.markdown(
        '<div class="diq-section-title">🩺&nbsp; What Happened to You</div>',
        unsafe_allow_html=True,
    )

    # "At a glance" block: labelled headers + teal pill badge bullets for
    # primary and secondary diagnoses, rendered above the Agent 2 text so
    # the patient immediately sees what they were treated for.
    primary_dx = _clean_str(ext.get("primary_diagnosis") or "")
    rows_html = ""
    if primary_dx:
        rows_html += (
            '<div class="diq-dx-label">Your main condition</div>'
            '<div class="diq-dx-row">'
            '<span class="diq-dx-badge"></span>'
            f'<span>{primary_dx}</span>'
            '</div>'
        )
    if secondary:
        sec_items = "".join(
            '<div class="diq-dx-row">'
            '<span class="diq-dx-badge"></span>'
            f'<span>{_clean_str(dx)}</span>'
            '</div>'
            for dx in secondary
            if _clean_str(dx)
        )
        rows_html += (
            '<div class="diq-dx-label">Other conditions treated during your stay</div>'
            + sec_items
        )
    if rows_html:
        st.markdown(rows_html + '<hr class="diq-dx-sep">', unsafe_allow_html=True)

    if explanation:
        # Agent 2 emits markdown (headers wrapped in **bold**, bullet lists).
        # Passing the text directly to st.markdown() lets Streamlit's
        # CommonMark parser render it. Do NOT wrap the output in a raw
        # <div> with unsafe_allow_html=True — CommonMark does not parse
        # markdown inside block-level HTML, so **bold** would come through
        # as literal asterisks.
        st.markdown(explanation)
    else:
        _empty_generation_message(result, "This explanation")

    chip_col, fk_col = st.columns([1, 4])
    with chip_col:
        if source and source.get("page"):
            _citation_button(
                source["page"],
                source.get("text", ""),
                key_suffix="dx",
            )

    with fk_col:
        pass


# ── Section: Medications ─────────────────────────────────────────────────────

def _parse_medication_rationale(text: str) -> dict[str, dict]:
    """
    Parse Agent 3's medication_rationale string into a per-drug lookup.

    Agent 3 emits one block per medication, blocks separated by a blank
    line. The first line of each block is "DrugName:" for normal meds or
    "DrugName — stopping:" for discontinued meds. Remaining lines in the
    block are the patient-facing paragraph(s).

    Args:
        text: The full medication_rationale string from PipelineResponse.

    Returns:
        dict keyed by lowercased drug name. Each value is a dict with:
            text     (str)  — the paragraph body, leading/trailing space trimmed
            stopping (bool) — True for discontinued/stopped medications
        Returns {} when text is empty or unparseable.
    """
    blocks: dict[str, dict] = {}
    if not text:
        return blocks

    for raw_block in text.split("\n\n"):
        block = raw_block.strip()
        if not block:
            continue
        # First line is the header ("Name:" or "Name — stopping:"); rest is body.
        head, _, body = block.partition("\n")
        body = body.strip()
        if not head.endswith(":") or not body:
            continue
        header = head[:-1].strip()
        # Detect the discontinued variant — the prompt uses an em dash but
        # we accept a plain hyphen too in case the model substitutes one.
        is_stopping = False
        for marker in (" — stopping", " - stopping"):
            if header.lower().endswith(marker):
                header = header[: -len(marker)].strip()
                is_stopping = True
                break
        name_key = header.lower()
        if name_key:
            blocks[name_key] = {"text": body, "stopping": is_stopping}
    return blocks


def _find_rationale_for_med(med_name: str, blocks: dict[str, dict]) -> dict | None:
    """
    Look up the Agent 3 rationale block matching a given medication name.

    Tries an exact case-insensitive match first, then falls back to a
    prefix match in either direction so qualifiers like "Aspirin 81mg"
    (extraction) still resolve to "Aspirin" (rationale) and vice versa.

    Args:
        med_name: The medication name from extraction.medications[*].name.
        blocks:   The dict returned by _parse_medication_rationale().

    Returns:
        The matching block dict (keys: text, stopping), or None when no
        block matches — caller skips rendering silently in that case.
    """
    if not med_name or not blocks:
        return None
    needle = med_name.strip().lower()
    if not needle:
        return None
    if needle in blocks:
        return blocks[needle]
    for key, val in blocks.items():
        if key.startswith(needle) or needle.startswith(key):
            return val
    return None


def _render_medication_card(
    med: dict,
    card_index: int,
    result: dict | None = None,
    rationale_block: dict | None = None,
) -> None:
    """
    Render a single medication card with status badge, caregiver questions,
    and the "Why you're taking this" toggle — all inside one bordered surface.

    The caregiver questions (from Agent 6) and the rationale toggle are
    embedded as inline HTML inside the card div so Streamlit renders them
    in a single st.markdown call, preventing content from leaking outside
    the card container.

    Args:
        med:            Medication dict from ExtractionOutput.
        card_index:     Zero-based index for unique widget keys.
        result:         PipelineResponse dict, for caregiver question lookup.
        rationale_block: Pre-matched rationale dict from _find_rationale_for_med,
                         or None when no rationale text was found.
    """
    name = _clean_str(med.get("name")) or "Unknown"
    dose = _clean_str(med.get("dose"))
    freq = _clean_str(med.get("frequency"))
    duration = _clean_str(med.get("duration"))
    status = _clean_str(med.get("status")).lower()
    source = med.get("source")

    border_color = _MED_BORDER.get(status, "#CBD5E1")
    badge_colors = {
        "new": "#185FA5",
        "changed": "#BA7517",
        "continued": "#3B6D11",
        "discontinued": "#A32D2D",
    }
    badge_color = badge_colors.get(status, "#64748B")
    badge_label = status.upper() if status else ""

    details = " · ".join(x for x in [dose, freq, duration] if x)
    changed_banner = (
        '<div class="diq-changed-banner">'
        "This changed from your previous prescription"
        "</div>"
    ) if status == "changed" else ""

    # Build inline caregiver questions HTML (empty string if none match).
    questions_html = ""
    if result is not None:
        questions_html = _caregiver_questions_inline_html(
            result,
            item_type="medication",
            label_candidates=[med.get("name", "") or ""],
        )

    # Build inline <details> rationale toggle (empty string when no block).
    details_toggle_html = ""
    if rationale_block:
        toggle_label = (
            "Why your doctor stopped this"
            if rationale_block.get("stopping")
            else "Why you're taking this and what to expect"
        )
        body_html = _simple_md_to_html(rationale_block.get("text", "") or "")
        details_toggle_html = (
            f'<details class="diq-html-details">'
            f'<summary>{_clean_str(toggle_label)}</summary>'
            f'<div class="diq-html-details-body">{body_html}</div>'
            f'</details>'
        )

    badge_html = (
        f"<span class='diq-badge' style='background:{badge_color};'>{badge_label}</span>"
        if badge_label else ""
    )

    st.markdown(
        f'<div class="diq-med-card" style="border-left-color:{border_color};">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;">'
        f'<span style="font-weight:700;font-size:0.95rem;color:#1E293B;">{name}</span>'
        f'{badge_html}'
        f'</div>'
        f'<div style="font-size:0.82rem;color:#64748B;margin-top:2px;">{details}</div>'
        f'{changed_banner}'
        f'{questions_html}'
        f'{details_toggle_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    if source and source.get("page"):
        _citation_button(
            source["page"],
            source.get("text", ""),
            key_suffix=f"med_{card_index}",
        )


def _render_section_medications(result: dict) -> None:
    """
    Render the medications tab — section title and one card per drug.

    Args:
        result: PipelineResponse dict.
    """
    ext = result.get("extraction", {})
    medications = ext.get("medications", [])

    st.markdown(
        '<div class="diq-section-title">💊&nbsp; Your Medications</div>',
        unsafe_allow_html=True,
    )

    _render_agent6_gap_callout(
        result,
        ["medication", "medicine", "drug", "dose", "dosage", "pill",
         "tablet", "inhaler", "inject", "insulin", "prescription", "refill"],
    )

    if not medications:
        st.caption("No medications found in the document.")
        return

    rationale_blocks = _parse_medication_rationale(
        _strip_em_dashes(result.get("medication_rationale", ""))
    )

    for idx, med in enumerate(medications):
        # Look up the rationale block here so it can be passed into the card
        # renderer and embedded inline inside the same bordered container.
        block = _find_rationale_for_med(med.get("name", ""), rationale_blocks)
        _render_medication_card(med, idx, result=result, rationale_block=block)

    rationale_raw = (result.get("medication_rationale") or "").strip()
    if medications and not rationale_raw:
        st.markdown("---")
        _empty_generation_message(result, "Medication explanations")


# ── Section: Appointments ────────────────────────────────────────────────────

def _render_appointment_row(
    appt: dict,
    row_index: int,
    result: dict | None = None,
) -> None:
    """
    Render a single follow-up appointment row.

    Caregiver questions from Agent 6 are embedded inline inside the same
    bordered card so the patient sees them as part of the appointment detail
    rather than a floating block below it.

    Every string field is run through _clean_str() before being embedded
    into the unsafe_allow_html markdown block — this is the defensive
    fix for upstream LLM responses that occasionally return HTML-laden
    reason/notes fields.

    Args:
        appt:      FollowUpAppointment dict from ExtractionOutput.
        row_index: Zero-based index for unique widget keys.
        result:    PipelineResponse dict, for caregiver question lookup.
    """
    provider = _clean_str(appt.get("provider"))
    specialty = _clean_str(appt.get("specialty"))
    reason = _clean_str(appt.get("reason"))
    # "notes" is not part of the canonical schema but some downstream
    # pipelines do populate it — strip defensively in case it shows up.
    notes = _clean_str(appt.get("notes"))
    raw_date = appt.get("date")
    date_display = _clean_str(_format_date(raw_date))
    source = appt.get("source")

    display_name = provider or specialty or "Appointment"
    sub_label = specialty if provider and specialty else ""
    details = reason or notes

    # Pick the timing affordance based on what the agent gave us:
    #   • Real ISO date  → 📅 calendar emoji + formatted date
    #   • Relative prose → ⏱ clock emoji + verbatim phrase ("in 7-10 days")
    #   • Nothing at all → suppress the timing line entirely so the row
    #                       doesn't loudly say "Date not specified"
    if _date_is_iso(raw_date):
        timing_html = (
            f"<div style='font-size:0.85rem;color:#374151;margin-top:2px;'>"
            f"{_CAL_ICON_SVG}{date_display}</div>"
        )
    elif raw_date and str(raw_date).strip():
        timing_html = (
            f"<div style='font-size:0.85rem;color:#374151;margin-top:2px;'>"
            f"⏱ {date_display}</div>"
        )
    else:
        timing_html = ""

    sub_html = (
        f"<span style='font-size:0.8rem;color:#64748B;margin-left:6px;'>"
        f"{sub_label}</span>"
        if sub_label else ""
    )
    details_html = (
        f"<div style='font-size:0.82rem;color:#64748B;'>{details}</div>"
        if details else ""
    )

    # Build the inner content as one concatenated HTML string with NO blank
    # lines. CommonMark treats a whitespace-only line as a block-terminator
    # for Type-6 HTML blocks (anything starting with `<div>`, `<p>`, etc.) —
    # so when timing_html or details_html was empty, the f-string produced a
    # blank line in the middle of the block, the parser switched back to
    # Markdown mode, and the trailing `</div>` closers (and any HTML inside
    # the next interpolation) rendered as visible text. Concatenating into a
    # single line avoids that whole class of failure.
    inner_parts = [
        f'<div style="font-weight:700;font-size:0.93rem;color:#1E293B;">'
        f'{display_name}{sub_html}</div>'
    ]
    if timing_html:
        inner_parts.append(timing_html)
    if details_html:
        inner_parts.append(details_html)
    inner_html = "".join(inner_parts)

    # Build inline caregiver questions HTML (empty string if none match).
    questions_html = ""
    if result is not None:
        questions_html = _caregiver_questions_inline_html(
            result,
            item_type="appointment",
            label_candidates=[
                appt.get("provider", "") or "",
                appt.get("specialty", "") or "",
            ],
        )

    st.markdown(
        '<div class="diq-appt-row">'
        '<div class="diq-appt-dot"></div>'
        f'<div style="flex:1;">{inner_html}{questions_html}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if source and source.get("page"):
        _citation_button(
            source["page"],
            source.get("text", ""),
            key_suffix=f"appt_{row_index}",
        )


def _appointment_sort_key(appt: dict) -> tuple:
    """
    Return a (priority, numeric_value) sort key for chronological ordering.

    Priority tiers:
      0 — ISO calendar date (YYYY-MM-DD), sorted by date value
      1 — relative phrase with a recognisable number ("in 7 days", "in 2 weeks")
      2 — other non-empty date string (e.g. "as soon as possible")
      3 — no date at all (null / empty)

    Within tier 1, relative offsets are normalised to days so that
    "in 3 days" < "in 2 weeks" < "in 2 months".
    """
    import re as _re
    from datetime import datetime as _dt

    date_str = (appt.get("date") or "").strip()
    if not date_str:
        return (3, 0)

    try:
        parsed = _dt.strptime(date_str, "%Y-%m-%d")
        return (0, parsed.timestamp())
    except ValueError:
        pass

    # Relative phrase — extract the first number and unit
    m = _re.search(r"(\d+)[\s\-]*(?:to[\s\-]*\d+\s*)?day", date_str, _re.IGNORECASE)
    if m:
        return (1, int(m.group(1)))
    m = _re.search(r"(\d+)[\s\-]*(?:to[\s\-]*\d+\s*)?week", date_str, _re.IGNORECASE)
    if m:
        return (1, int(m.group(1)) * 7)
    m = _re.search(r"(\d+)[\s\-]*(?:to[\s\-]*\d+\s*)?month", date_str, _re.IGNORECASE)
    if m:
        return (1, int(m.group(1)) * 30)

    return (2, 0)


def _render_section_appointments(result: dict) -> None:
    """
    Render the appointments tab, sorted chronologically (soonest first).

    ISO dates sort before relative phrases ("in 7 days"), which sort before
    appointments with no timing information.

    Args:
        result: PipelineResponse dict.
    """
    ext = result.get("extraction", {})
    appointments = ext.get("follow_up_appointments", [])

    st.markdown(
        '<div class="diq-section-title">📅&nbsp; Your Follow-Up Appointments</div>',
        unsafe_allow_html=True,
    )

    if not appointments:
        st.caption("No follow-up appointments found in the document.")
        return

    sorted_appointments = sorted(appointments, key=_appointment_sort_key)
    for idx, appt in enumerate(sorted_appointments):
        # Caregiver questions are now embedded inside the appointment card.
        _render_appointment_row(appt, idx, result=result)


# ── Section: Warning signs ───────────────────────────────────────────────────

# Tier header strings from agent5_system_prompt.txt. These must match the
# prompt output exactly. If the prompt ever changes a header, update this
# list in lock-step or the escalation tab goes blank.
_ESCALATION_TIER_HEADERS = (
    "CALL 911 IMMEDIATELY",
    "GO TO THE ER TODAY",
    "CALL YOUR DOCTOR",
)

# Per-tier styling — (background, border, heading color, subtitle color,
# bullet-text color, accent-dot color). Red for 911 (urgency), amber for
# ER (caution), yellow for doctor (information). Colors deliberately mirror
# the existing diq-warning-card palette so the tab doesn't clash visually.
_ESCALATION_TIER_STYLES = {
    "CALL 911 IMMEDIATELY": {
        "bg": "#FEE2E2", "border": "#FCA5A5",
        "head": "#7F1D1D", "sub": "#991B1B",
        "body": "#7F1D1D", "dot": "#DC2626",
    },
    "GO TO THE ER TODAY": {
        "bg": "#FFEDD5", "border": "#FDBA74",
        "head": "#7C2D12", "sub": "#9A3412",
        "body": "#7C2D12", "dot": "#EA580C",
    },
    "CALL YOUR DOCTOR": {
        "bg": "#FEF3C7", "border": "#FCD34D",
        "head": "#78350F", "sub": "#92400E",
        "body": "#78350F", "dot": "#D97706",
    },
}


def _parse_escalation_guide(text: str) -> list[dict]:
    """
    Parse the plain-text three-tier escalation guide produced by Agent 5
    into structured blocks for rendering.

    Expected input shape (from agent5_system_prompt.txt):

        CALL 911 IMMEDIATELY
        These symptoms are life-threatening. Do not drive yourself.
        - Symptom A: explanation sentence.
        - Symptom B: explanation sentence.

        GO TO THE ER TODAY
        Do not wait until tomorrow. Go within a few hours.
        - Symptom C: ...
        ...

    Missing tiers, extra blank lines, and bullets that use "•" instead of
    "-" are all tolerated — the function is defensive so a small Agent 5
    format drift never blanks the whole tab.

    Args:
        text: Full Agent 5 output string.

    Returns:
        list[dict]: Zero to three tier dicts, in the order headers appeared.
                    Each dict has keys:
                        header   (str) — exact header string (upper case)
                        subtitle (str) — one-line sentence under the header
                        bullets  (list[str]) — each bullet with the leading
                                                dash/space stripped
    """
    if not text:
        return []

    lines = [line.rstrip() for line in text.splitlines()]
    blocks: list[dict] = []
    current: dict | None = None

    # A "subtitle pending" flag lets us grab the first non-empty
    # non-bullet line after a header as the subtitle without misclassifying
    # it as a bullet.
    subtitle_pending = False

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue

        if stripped in _ESCALATION_TIER_HEADERS:
            if current is not None:
                blocks.append(current)
            current = {"header": stripped, "subtitle": "", "bullets": []}
            subtitle_pending = True
            continue

        if current is None:
            # Preamble before the first header — ignore.
            continue

        # Bullets use "- " or occasionally "• "; everything else under a
        # header is treated as continuation of the subtitle or prose.
        if stripped.startswith("- ") or stripped.startswith("• "):
            current["bullets"].append(stripped[2:].strip())
            subtitle_pending = False
        elif subtitle_pending:
            current["subtitle"] = stripped
            subtitle_pending = False
        else:
            # Defensive: treat stray lines as appended bullets rather than
            # dropping them — a safety agent's words should not disappear.
            current["bullets"].append(stripped)

    if current is not None:
        blocks.append(current)

    return blocks


def _render_escalation_tier(block: dict) -> None:
    """
    Render one parsed escalation-tier block as a coloured card.

    Args:
        block: Dict with keys header, subtitle, bullets (see
               _parse_escalation_guide). Header must be one of the
               three known strings in _ESCALATION_TIER_STYLES — unknown
               headers are rendered in a neutral slate palette.
    """
    style = _ESCALATION_TIER_STYLES.get(block["header"], {
        "bg": "#F1F5F9", "border": "#CBD5E1",
        "head": "#0F172A", "sub": "#334155",
        "body": "#1E293B", "dot": "#64748B",
    })

    bullets_html = "".join(
        f'<div style="display:flex;gap:8px;align-items:flex-start;'
        f'margin-top:6px;">'
        f'<div style="min-width:6px;width:6px;height:6px;border-radius:50%;'
        f'background:{style["dot"]};margin-top:7px;"></div>'
        f'<div style="font-size:0.9rem;color:{style["body"]};'
        f'line-height:1.4;">{_clean_str(bullet)}</div>'
        f"</div>"
        for bullet in block["bullets"]
    )

    subtitle_html = (
        f'<div style="font-size:0.82rem;color:{style["sub"]};'
        f'margin-top:2px;margin-bottom:6px;">'
        f"{_clean_str(block['subtitle'])}</div>"
        if block.get("subtitle")
        else ""
    )

    st.markdown(
        f'<div style="background:{style["bg"]};border:1px solid {style["border"]};'
        f'border-radius:12px;padding:14px 16px;margin-top:10px;">'
        f'<div style="font-weight:700;font-size:0.95rem;color:{style["head"]};'
        f'letter-spacing:0.04em;">{block["header"]}</div>'
        f"{subtitle_html}"
        f"{bullets_html}"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_section_warning_signs(result: dict) -> None:
    """
    Render the warning-signs tab — the flat red-flag list from Agent 1
    stays at the top as a quick reference, followed by the Agent 5
    three-tier escalation guide (911 / ER / call doctor) rendered as
    colour-coded cards.

    No citation chips here per safety-spec: the patient should not need
    to interact with the content to read it. Agent 5 output is parsed
    defensively — format drift must not blank the tab.

    Args:
        result: PipelineResponse dict.
    """
    ext = result.get("extraction", {})
    flags = ext.get("red_flag_symptoms", [])
    escalation = _clean_str(result.get("escalation_guide", ""))

    st.markdown(
        '<div class="diq-section-title">🚨&nbsp; Warning Signs</div>',
        unsafe_allow_html=True,
    )

    st.info(
        "**Important:** This warning-signs guide is **AI-generated** and may be "
        "incomplete or incorrect. **Call your care team** to confirm what symptoms "
        "require emergency care for your situation. For life-threatening "
        "emergencies, call **911** (or your local emergency number)."
    )

    _render_agent6_gap_callout(
        result,
        ["symptom", "emergency", "911", "er ", "warning", "sign", "fever",
         "pain", "breathe", "bleeding", "swelling", "dizzy", "chest", "call"],
    )

    if not flags and not escalation:
        st.caption("No emergency warning signs listed in the document.")
        return

    if flags:
        # Build each flag row followed immediately by its caregiver questions
        # — all inside the same red-tinted warning card so they render as one
        # bordered surface rather than a stacked second card per flag.
        flag_blocks_html = ""
        for flag in flags:
            flag_row = (
                f'<div class="diq-flag-row">'
                f'<div class="diq-flag-dot"></div>'
                f'<div style="font-size:0.9rem;color:#7F1D1D;">{_clean_str(flag)}</div>'
                f'</div>'
            )
            inline_q = _caregiver_questions_inline_html(
                result,
                item_type="warning_sign",
                label_candidates=[flag or ""],
            )
            flag_blocks_html += flag_row + inline_q

        st.markdown(
            '<div class="diq-warning-card">'
            '<div style="font-weight:700;font-size:0.9rem;color:#7F1D1D;margin-bottom:8px;">'
            "Go to the ER or call 911 if you have:"
            "</div>"
            f"{flag_blocks_html}"
            "</div>",
            unsafe_allow_html=True,
        )

    if escalation:
        blocks = _parse_escalation_guide(escalation)
        if blocks:
            st.markdown("---")
            st.markdown("#### What to do if you have these symptoms")
            for block in blocks:
                _render_escalation_tier(block)
        else:
            st.markdown("---")
            _empty_generation_message(
                result,
                "The step-by-step escalation guide (when to call 911 / your doctor)",
            )


# ── Section: Recovery ────────────────────────────────────────────────────────

def _render_section_recovery(result: dict) -> None:
    """
    Render the recovery tab — activity restrictions (left) and dietary
    restrictions (right) with discharge condition beneath.

    Args:
        result: PipelineResponse dict.
    """
    ext = result.get("extraction", {})
    activity = ext.get("activity_restrictions", [])
    dietary = ext.get("dietary_restrictions", [])
    condition = _clean_str(ext.get("discharge_condition"))

    st.markdown(
        '<div class="diq-section-title">🗓️&nbsp; Recovery Notes</div>',
        unsafe_allow_html=True,
    )

    col_act, col_diet = st.columns(2)

    with col_act:
        st.markdown(
            '<div style="font-size:0.85rem;font-weight:600;color:#1E293B;'
            'margin-bottom:6px;">Activity</div>',
            unsafe_allow_html=True,
        )
        activity_items = [_clean_str(item) for item in activity if _clean_str(item)]
        if activity_items:
            st.markdown("\n".join(f"- {item}" for item in activity_items))
        else:
            st.caption("None listed.")

    with col_diet:
        st.markdown(
            '<div style="font-size:0.85rem;font-weight:600;color:#1E293B;'
            'margin-bottom:6px;">Diet</div>',
            unsafe_allow_html=True,
        )
        dietary_items = [_clean_str(item) for item in dietary if _clean_str(item)]
        if dietary_items:
            st.markdown("\n".join(f"- {item}" for item in dietary_items))
        else:
            st.caption("None listed.")

    if condition:
        st.markdown(
            f'<div class="diq-discharge-cond">'
            f'<b>Condition at discharge:</b> {condition}'
            f'</div>',
            unsafe_allow_html=True,
        )

    trajectory = _strip_em_dashes((result.get("recovery_trajectory") or "").strip())
    st.markdown("---")
    st.markdown("#### Your recovery timeline")
    # Plain-language scope note. The timeline is a per-week summary of Agent
    # 4's narrative; the verbatim activity, diet, and condition rules from
    # the discharge document already render in the boxes above this section,
    # and the "Verify what the AI extracted" expander on the AI Review tab
    # shows the full structured extraction with citations.
    st.markdown(
        '<div style="background:#F0FDF9;border:1px solid rgba(29,158,117,0.25);'
        'border-radius:8px;padding:8px 12px;margin:6px 0 14px;'
        'font-size:0.82rem;color:#0F4C3A;">'
        'This is a plain-language summary of what to expect each week. '
        'Your full activity and diet rules are in the boxes above. '
        'For the exact wording from your discharge document, open '
        '<b>Verify what the AI extracted</b> on the <b>AI Review</b> tab '
        'or click any <b>Page N</b> chip (the page number from your discharge document) to jump to that page.'
        '</div>',
        unsafe_allow_html=True,
    )
    if trajectory:
        _render_recovery_trajectory(trajectory)
    else:
        _empty_generation_message(result, "Your recovery timeline")


_WEEK_HEADER_RE = re.compile(
    r"\*\*\s*(Week\s+[0-9]+(?:\s*[-–]\s*[0-9]+)?\s*:?)\s*\*\*",
    flags=re.IGNORECASE,
)
_OUTRO_HEADER_RE = re.compile(
    r"\*\*\s*(When\s+to\s+expect\s+improvement\s*:?)\s*\*\*",
    flags=re.IGNORECASE,
)


def _parse_recovery_trajectory(text: str) -> tuple[list[dict], str]:
    """
    Split Agent 4's recovery trajectory into per-week sections plus the
    closing "When to expect improvement" paragraph.

    Agent 4's prompt fixes the format as bold headers like **Week 1:**,
    **Week 2:**, **Week 3-4:**, and a final **When to expect improvement:**.
    This parser is defensive: it tolerates spacing variations, missing
    colons, and the occasional rogue bullet so the recovery tab never
    blanks just because the LLM reformatted slightly.

    Args:
        text: The recovery_trajectory string from PipelineResponse.

    Returns:
        Tuple (weeks, outro):
            weeks: list of {"header": "Week N:", "body": "..."} dicts in
                   document order. body has the original line breaks
                   preserved so per-week markdown still renders cleanly.
            outro: the closing "When to expect improvement" paragraph,
                   without its bold header (renderer adds its own).
                   Empty string when absent.
    """
    if not text:
        return [], ""

    # Pull off the outro paragraph first so its body doesn't get absorbed
    # into the last week section.
    outro = ""
    outro_match = _OUTRO_HEADER_RE.search(text)
    if outro_match:
        outro = text[outro_match.end():].strip()
        text = text[: outro_match.start()].strip()

    weeks: list[dict] = []
    matches = list(_WEEK_HEADER_RE.finditer(text))
    if not matches:
        # No structured week headers — fall back to a single block.
        if text.strip():
            weeks.append({"header": "Recovery", "body": text.strip()})
        return weeks, outro

    for idx, match in enumerate(matches):
        header_raw = match.group(1).strip()
        if not header_raw.endswith(":"):
            header_raw = f"{header_raw}:"
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        weeks.append({"header": header_raw, "body": body})

    return weeks, outro


def _render_recovery_trajectory(trajectory: str) -> None:
    """
    Render Agent 4's recovery trajectory as colour-cycled per-week cards
    plus a final summary banner for "When to expect improvement".

    Cards reduce the wall-of-text effect that prose paragraphs produced
    while preserving every sentence Agent 4 emitted. Each card:
        - Shows a teal-numbered badge on the left ("W1", "W2", ...).
        - Lays out the week body at a comfortable 1.55 line height.
        - Stacks vertically with consistent spacing.

    If the trajectory text doesn't match the expected week format, the
    parser falls back to a single block so we never lose content.
    """
    weeks, outro = _parse_recovery_trajectory(trajectory)

    if not weeks and not outro:
        # Last resort: render the raw text. Better to show prose than nothing.
        st.markdown(trajectory)
        return

    for idx, week in enumerate(weeks, start=1):
        header = _clean_str(week["header"])
        # Convert week body markdown to inline HTML so the whole card
        # (header card + body) lives in ONE st.markdown call. Two calls
        # would leak the body content outside the green-bordered card
        # because Streamlit puts each markdown call in its own DOM div.
        body_html = _simple_md_to_html(week["body"].strip())
        st.markdown(
            f'<div class="diq-week-card">'
            f'<div class="diq-week-badge">W{idx}</div>'
            f'<div class="diq-week-header">{header}</div>'
            f'</div>'
            f'<div class="diq-week-body">{body_html}</div>',
            unsafe_allow_html=True,
        )

    if outro:
        # Same single-call pattern for the outro card. Bullets in `outro`
        # are now valid markdown, so we pre-convert to HTML and embed.
        outro_html = _simple_md_to_html(outro)
        st.markdown(
            f'<div class="diq-week-outro">'
            f'<div class="diq-week-outro-label">When to expect improvement</div>'
            f'<div class="diq-week-outro-body">{outro_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Agent 6 cross-tab gap callout ────────────────────────────────────────────

def _render_agent6_gap_callout(result: dict, topic_keywords: list[str]) -> None:
    """
    Render a small Agent 6 callout if any unanswered critical/moderate concept
    matches the given topic keywords (e.g. ["medication", "drug", "dose"]).

    Called at the top of relevant tabs (Medications, Warning Signs) so the
    patient sees related gaps in context rather than only in the AI Review tab.

    Args:
        result:         PipelineResponse dict.
        topic_keywords: Lowercase strings; a concept matches if any keyword
                        appears in the question or gap_summary text.
    """
    sim = result.get("patient_simulator")
    if not sim:
        return
    concepts = sim.get("missed_concepts") or []
    relevant = [
        c for c in concepts
        if not c.get("answered_by_doc", True)
        and c.get("severity") in ("critical", "moderate")
        and any(
            kw in (c.get("question", "") + " " + c.get("gap_summary", "")).lower()
            for kw in topic_keywords
        )
    ]
    if not relevant:
        return
    items_html = "".join(
        f'<li style="margin-bottom:3px;">{_clean_str(c.get("question",""))}</li>'
        for c in relevant[:3]
    )
    st.markdown(
        f'<div style="background:#FFFBEB;border:1px solid #FCD34D;border-radius:8px;'
        f'padding:10px 14px;margin-bottom:14px;">'
        f'<div style="font-size:0.78rem;font-weight:700;color:#78350F;margin-bottom:4px;">'
        f'AI Review flagged {len(relevant)} unanswered question'
        f'{"s" if len(relevant) > 1 else ""} in this area</div>'
        f'<ul style="margin:0;padding-left:18px;font-size:0.82rem;color:#92400E;">'
        f'{items_html}</ul>'
        f'<div style="font-size:0.75rem;color:#B45309;margin-top:6px;">'
        f'See the <em>AI Review</em> tab for full details.</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _match_caregiver_questions(
    result: dict,
    item_type: str,
    label_candidates: list[str],
) -> list[str]:
    """
    Return the deduplicated list of caregiver question strings for one item.

    Shared matching logic used by both the standalone renderer and the
    inline HTML builder so the two paths always show the same questions.

    Args:
        result:           PipelineResponse dict.
        item_type:        Agent 6 item_type string ("medication", "appointment", etc.)
        label_candidates: Strings fuzzy-matched (substring) against item_label.

    Returns:
        List of plain question strings (already cleaned), capped at 3.
        Empty list when nothing matches or patient_simulator is absent.
    """
    sim = result.get("patient_simulator")
    if not sim:
        return []
    questions = sim.get("caregiver_questions") or []
    if not questions:
        return []

    cleaned_candidates = [
        c.lower().strip() for c in label_candidates if c and c.strip()
    ]
    if not cleaned_candidates:
        return []

    import re as _re

    def _label_tokens(s: str) -> list[str]:
        # All alpha runs of length >= 4 — meaningful words like specialty
        # names, provider surnames. Filters out "Dr", "Mr", middle initials.
        return [w for w in _re.findall(r'[a-z]+', s.lower()) if len(w) >= 4]

    matching: list[dict] = []
    for entry in questions:
        if entry.get("item_type") != item_type:
            continue
        entry_label = (entry.get("item_label") or "").lower().strip()
        if not entry_label:
            continue
        # Fast path: whole-string substring (works when labels align exactly).
        if any(cand in entry_label or entry_label in cand
               for cand in cleaned_candidates):
            matching.append(entry)
            continue
        # Token fallback: any meaningful word from a candidate found in the
        # entry_label. Handles middle initials ("Dr. M. Okonkwo" → "okonkwo")
        # and slash-separated specialties ("Pulmonology/Cardiology" → each word).
        cand_tokens = [t for c in cleaned_candidates for t in _label_tokens(c)]
        if cand_tokens and any(tok in entry_label for tok in cand_tokens):
            matching.append(entry)

    all_questions: list[str] = []
    seen: set[str] = set()
    for entry in matching:
        for q in entry.get("questions") or []:
            qq = _clean_str(q)
            if qq and qq.lower() not in seen:
                seen.add(qq.lower())
                all_questions.append(qq)

    return all_questions[:3]


def _caregiver_questions_inline_html(
    result: dict,
    item_type: str,
    label_candidates: list[str],
) -> str:
    """
    Return the "ASK YOUR CARE TEAM" block as an HTML string for embedding
    inside a card's <div> in a single st.markdown call.

    Returns an empty string when no matching questions exist so the caller
    can interpolate unconditionally without emitting an empty div.

    Args:
        result:           PipelineResponse dict.
        item_type:        Agent 6 item_type string.
        label_candidates: Strings matched against item_label.

    Returns:
        HTML string or "".
    """
    all_questions = _match_caregiver_questions(result, item_type, label_candidates)
    if not all_questions:
        return ""

    items_html = "".join(
        f'<li>{q}</li>'
        for q in all_questions
    )
    return (
        '<div class="diq-caregiver-questions-inline">'
        '<div style="font-size:0.72rem;font-weight:700;color:#075985;'
        'text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">'
        '💬 Ask your care team</div>'
        f'<ul>{items_html}</ul>'
        '</div>'
    )


def _render_caregiver_questions_for_item(
    result: dict,
    item_type: str,
    label_candidates: list[str],
) -> None:
    """
    Render a small "Ask your caregiver" block under one extracted item.

    Looks up Agent 6's per-item caregiver questions
    (`patient_simulator.caregiver_questions`) and renders any whose
    `item_type` matches and whose `item_label` fuzzy-matches one of the
    provided candidates (substring, lowercased).

    The block is intentionally compact — patients see it inline next to the
    relevant card so they can act on the gap item-by-item, per the
    professor's demo feedback that questions should attach to "each one"
    rather than only living in a global review tab.

    Args:
        result:           PipelineResponse dict.
        item_type:        One of "medication", "appointment", "warning_sign",
                          "diagnosis", or "diet_activity" — must match the
                          Agent 6 schema.
        label_candidates: Strings that should match (substring,
                          case-insensitive) against the LLM's item_label.
                          For a medication this is typically [name];
                          for an appointment, [provider, specialty];
                          for a warning sign, [flag_text].
    """
    html_block = _caregiver_questions_inline_html(result, item_type, label_candidates)
    if html_block:
        st.markdown(html_block, unsafe_allow_html=True)


# ── Section: AI Patient Simulator (Agent 6) ──────────────────────────────────

_SIM_SEVERITY_COLORS = {
    "critical": ("#7F1D1D", "#FEE2E2", "#FCA5A5"),   # text, bg, border
    "moderate": ("#78350F", "#FEF3C7", "#FCD34D"),
    "minor":    ("#1E3A5F", "#EFF6FF", "#BFDBFE"),
}


def _render_extraction_verification(result: dict) -> None:
    """
    Render the "Verify what the AI extracted" expander.

    Surfaces the structured Agent 1 extraction so the patient or caregiver
    can spot-check that the data underlying every other tab is correct.
    For each populated field we show a ✅ when a SourceSpan citation is
    available (Agent 1 grounded the field in a verbatim PDF quote) and a
    ⚠️ when the field exists but has no provenance.

    The expander lives inside the AI Review tab so the "AI quality" framing
    is centralized — patients have one place to evaluate whether to trust
    what the system pulled.

    Args:
        result: PipelineResponse dict.
    """
    ext = result.get("extraction") or {}
    extraction_warnings = result.get("extraction_warnings") or []

    with st.expander("🔍  Verify what the AI extracted", expanded=False):
        st.caption(
            "Spot-check what the AI pulled from your discharge document. "
            "Click the page number on any row to see the original text. "
            "If anything looks wrong, ask your care team before following the "
            "AI's advice."
        )

        if extraction_warnings:
            warn_html = "".join(
                f'<li style="margin-bottom:2px;">{_clean_str(str(w))}</li>'
                for w in extraction_warnings
            )
            st.markdown(
                f'<div style="background:#FEF3C7;border:1px solid #FCD34D;'
                f'border-radius:6px;padding:8px 12px;margin-bottom:10px;">'
                f'<div style="font-size:0.78rem;font-weight:700;color:#78350F;'
                f'margin-bottom:4px;">Extraction warnings</div>'
                f'<ul style="margin:0;padding-left:18px;font-size:0.8rem;'
                f'color:#92400E;">{warn_html}</ul></div>',
                unsafe_allow_html=True,
            )

        _render_verification_scalar_rows(ext)
        _render_verification_medications(ext)
        _render_verification_appointments(ext)
        _render_verification_simple_lists(ext)


def _verification_scalar_row(
    field_label: str,
    value: str | None,
    source: dict | None,
    key_suffix: str,
) -> None:
    """
    Render one extracted-field row inside the verification expander.

    Layout: bold label, the extracted value, a ✅/⚠️ icon for whether a
    SourceSpan was attached, and (when a span is present) a citation chip
    that opens the PDF modal at the cited page.
    """
    cleaned_value = _clean_str(value) or "-"
    has_source = bool(source and source.get("page"))
    icon = "✅" if has_source else "⚠️"
    icon_tooltip = (
        "Grounded in a verbatim PDF quote"
        if has_source
        else "No source citation. Verify with caregiver."
    )

    cols = st.columns([1.2, 2.8, 0.4, 0.6])
    with cols[0]:
        st.markdown(
            f'<div style="font-size:0.82rem;color:#475569;font-weight:600;">'
            f'{_clean_str(field_label)}</div>',
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            f'<div style="font-size:0.85rem;color:#1E293B;">{cleaned_value}</div>',
            unsafe_allow_html=True,
        )
    with cols[2]:
        st.markdown(
            f'<div title="{icon_tooltip}" style="font-size:0.95rem;">{icon}</div>',
            unsafe_allow_html=True,
        )
    with cols[3]:
        if has_source:
            _citation_button(
                source["page"],
                source.get("text", ""),
                key_suffix=f"verify_{key_suffix}",
            )


def _render_verification_scalar_rows(ext: dict) -> None:
    """Render top-level scalar fields with their ✅/⚠️ verification status."""
    st.markdown(
        '<div style="font-size:0.78rem;font-weight:700;color:#475569;'
        'text-transform:uppercase;letter-spacing:0.05em;margin-top:8px;'
        'margin-bottom:6px;">Document Details</div>',
        unsafe_allow_html=True,
    )
    _verification_scalar_row(
        "Patient name", ext.get("patient_name"), None, "patient_name"
    )
    _verification_scalar_row(
        "Discharge date", ext.get("discharge_date"), None, "discharge_date"
    )
    _verification_scalar_row(
        "Primary diagnosis",
        ext.get("primary_diagnosis"),
        ext.get("primary_diagnosis_source"),
        "primary_dx",
    )
    _verification_scalar_row(
        "Discharge condition",
        ext.get("discharge_condition"),
        None,
        "discharge_cond",
    )


def _render_verification_medications(ext: dict) -> None:
    """Render extracted medications with per-row source citation status."""
    medications = ext.get("medications") or []
    if not medications:
        return
    st.markdown(
        '<div style="font-size:0.78rem;font-weight:700;color:#475569;'
        'text-transform:uppercase;letter-spacing:0.05em;margin-top:14px;'
        'margin-bottom:6px;">Medications</div>',
        unsafe_allow_html=True,
    )
    for idx, med in enumerate(medications):
        details = " · ".join(
            x for x in (
                _clean_str(med.get("dose")),
                _clean_str(med.get("frequency")),
                _clean_str(med.get("status")),
            ) if x
        )
        value = _clean_str(med.get("name") or "")
        if details:
            value = f"{value} ({details})" if value else details
        _verification_scalar_row(
            f"Med {idx + 1}",
            value,
            med.get("source"),
            f"med_{idx}",
        )


def _render_verification_appointments(ext: dict) -> None:
    """Render extracted follow-up appointments with source citation status."""
    appts = ext.get("follow_up_appointments") or []
    if not appts:
        return
    st.markdown(
        '<div style="font-size:0.78rem;font-weight:700;color:#475569;'
        'text-transform:uppercase;letter-spacing:0.05em;margin-top:14px;'
        'margin-bottom:6px;">Follow-up Appointments</div>',
        unsafe_allow_html=True,
    )
    for idx, appt in enumerate(appts):
        bits = [
            _clean_str(appt.get("provider")),
            _clean_str(appt.get("specialty")),
            _clean_str(appt.get("date")),
            _clean_str(appt.get("reason")),
        ]
        value = " · ".join(b for b in bits if b)
        _verification_scalar_row(
            f"Appt {idx + 1}",
            value,
            appt.get("source"),
            f"appt_{idx}",
        )


def _render_verification_simple_lists(ext: dict) -> None:
    """
    Render the unprovenanced list fields. SourceSpan is not currently
    captured for these fields by Agent 1's schema, so they always render
    with a ⚠️ icon and no citation chip — caregiver verification still
    matters here, just without a one-click jump.
    """
    sections = (
        ("Secondary diagnoses",   ext.get("secondary_diagnoses")),
        ("Procedures performed",  ext.get("procedures_performed")),
        ("Activity restrictions", ext.get("activity_restrictions")),
        ("Dietary restrictions",  ext.get("dietary_restrictions")),
        ("Red-flag symptoms",     ext.get("red_flag_symptoms")),
    )
    has_any = any(items for _, items in sections)
    if not has_any:
        return

    st.markdown(
        '<div style="font-size:0.78rem;font-weight:700;color:#475569;'
        'text-transform:uppercase;letter-spacing:0.05em;margin-top:14px;'
        'margin-bottom:6px;">Lists (no source citation)</div>',
        unsafe_allow_html=True,
    )
    for label, items in sections:
        items = items or []
        if not items:
            continue
        bullets = "".join(
            f'<li style="margin-bottom:2px;">{_clean_str(str(it))}</li>'
            for it in items
        )
        st.markdown(
            f'<div style="font-size:0.82rem;color:#1E293B;margin-bottom:10px;">'
            f'<span style="font-weight:600;color:#475569;">{label}:</span>'
            f'<ul style="margin:4px 0 0 0;padding-left:20px;color:#1E293B;">'
            f'{bullets}</ul></div>',
            unsafe_allow_html=True,
        )


def _render_section_simulator(result: dict) -> None:
    """
    Render the AI Review tab — Agent 6 patient-simulator output.

    Shows the overall gap score, simulator summary, and each missed concept
    (question the document failed to answer). Unanswered concepts are shown
    with a severity-coded card; answered ones are collapsed into a small list.

    Args:
        result: PipelineResponse dict containing optional 'patient_simulator' key.
    """
    st.markdown(
        '<div class="diq-section-title">🤖&nbsp; AI Patient Review</div>',
        unsafe_allow_html=True,
    )

    sim = result.get("patient_simulator")

    if not sim:
        st.info(
            "The AI gap finder did not run for this document. "
            "This can happen when the pipeline ran in partial mode or the agent timed out. "
            "Re-analyze the document to retry."
        )
        return

    # ── Human-in-the-loop notice ───────────────────────────────────────────────
    st.markdown(
        '<div style="background:#FFFBEB;border:1px solid #FCD34D;border-radius:8px;'
        'padding:12px 16px;margin-bottom:10px;font-size:0.88rem;color:#78350F;">'
        '<strong>For you to bring up with your care team:</strong> The AI noticed '
        'questions your discharge document may not fully answer. These are not '
        'medical diagnoses — bring them up with your nurse, doctor, or care '
        'coordinator before you go home.'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.78rem;color:#94A3B8;margin-top:2px;margin-bottom:16px;">'
        'Care coordinators: run this before the patient leaves to catch gaps in the '
        'discharge instructions before they go home.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Extraction verification ────────────────────────────────────────────────
    # Lets the user spot-check what Agent 1 pulled from the PDF before they
    # trust the agent-generated explanations. Lives in the AI Review tab so
    # all "AI quality" framing stays in one place.
    _render_extraction_verification(result)

    # ── Overall gap score ──────────────────────────────────────────────────────
    try:
        gap_score = max(0, min(10, int(float(sim.get("overall_gap_score", 0) or 0))))
    except (TypeError, ValueError):
        gap_score = 0
    summary = _clean_str(sim.get("simulator_summary", ""))

    if gap_score <= 3:
        bar_color   = "#1D9E75"
        score_label = "Low gap. Document covers most patient needs."
    elif gap_score <= 6:
        bar_color   = "#D97706"
        score_label = "Moderate gap. Patient likely has unanswered questions."
    else:
        bar_color   = "#C0392B"
        score_label = "High gap. Critical information may be missing."

    bar_pct = gap_score * 10
    st.markdown(
        f'<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;'
        f'padding:16px 20px;margin-bottom:16px;">'
        f'<div style="font-size:0.75rem;color:#64748B;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">'
        f'Overall Gap Score</div>'
        f'<div style="display:flex;align-items:center;gap:14px;">'
        f'<div style="font-size:2.2rem;font-weight:800;color:{bar_color};'
        f'line-height:1;">{gap_score}'
        f'<span style="font-size:1rem;color:#94A3B8;font-weight:400;"> / 10</span></div>'
        f'<div style="flex:1;">'
        f'<div style="background:#E5E7EB;border-radius:6px;height:8px;overflow:hidden;">'
        f'<div style="width:{bar_pct}%;height:100%;background:{bar_color};'
        f'border-radius:6px;"></div></div>'
        f'<div style="font-size:0.8rem;color:{bar_color};font-weight:600;margin-top:4px;">'
        f'{score_label}</div></div></div></div>',
        unsafe_allow_html=True,
    )

    if summary:
        st.markdown(
            f'<div style="background:#F0FDF9;border-left:3px solid #1D9E75;'
            f'padding:10px 14px;border-radius:4px;margin-bottom:16px;'
            f'font-size:0.88rem;color:#0F4C3A;">{summary}</div>',
            unsafe_allow_html=True,
        )

    # ── Missed concepts ────────────────────────────────────────────────────────
    concepts = sim.get("missed_concepts") or []
    if not concepts:
        st.caption("No concept questions returned by the simulator.")
        return

    gaps     = [c for c in concepts if not c.get("answered_by_doc", True)]
    answered = [c for c in concepts if c.get("answered_by_doc", True)]

    # Severity breakdown pill row.
    n_critical = sum(1 for c in gaps if (c.get("severity") or "") == "critical")
    n_moderate = sum(1 for c in gaps if (c.get("severity") or "") == "moderate")
    n_minor    = sum(1 for c in gaps if (c.get("severity") or "") == "minor")

    def _pill(count: int, label: str, color: str) -> str:
        if not count:
            return ""
        return (
            f'<span style="font-size:0.72rem;font-weight:700;color:{color};'
            f'background:rgba(0,0,0,0.05);border-radius:20px;padding:2px 10px;'
            f'margin-right:6px;">{count} {label}</span>'
        )

    if gaps:
        pills = (
            _pill(n_critical, "critical", "#C0392B")
            + _pill(n_moderate, "moderate", "#D97706")
            + _pill(n_minor, "minor", "#1E3A5F")
        )
        st.markdown(
            f'<div style="margin-bottom:10px;">{pills}</div>'
            f'<div style="font-size:0.8rem;font-weight:700;color:#64748B;'
            f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;">'
            f'Questions the document did not fully answer ({len(gaps)})</div>',
            unsafe_allow_html=True,
        )
        for concept in gaps:
            severity = (concept.get("severity") or "moderate").lower()
            txt_col, bg_col, bdr_col = _SIM_SEVERITY_COLORS.get(
                severity, _SIM_SEVERITY_COLORS["moderate"]
            )
            question = _clean_str(concept.get("question", ""))
            gap_text = _clean_str(concept.get("gap_summary", ""))
            badge    = severity.upper()
            st.markdown(
                f'<div style="background:{bg_col};border:1px solid {bdr_col};'
                f'border-radius:8px;padding:12px 16px;margin-bottom:8px;">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
                f'<span style="font-size:0.65rem;font-weight:700;color:{txt_col};'
                f'background:rgba(0,0,0,0.07);border-radius:4px;padding:1px 7px;">'
                f'{badge}</span>'
                f'<span style="font-size:0.9rem;font-weight:600;color:{txt_col};">'
                f'{question}</span></div>'
                + (
                    f'<div style="font-size:0.82rem;color:#475569;margin-top:4px;">'
                    f'{gap_text}</div>'
                    if gap_text and gap_text.upper() != "N/A"
                    else ""
                )
                + "</div>",
                unsafe_allow_html=True,
            )

    # ── Questions to bring to your care team ──────────────────────────────────
    questions_html = build_questions_section_html(gaps)
    if questions_html:
        st.markdown(questions_html, unsafe_allow_html=True)
        st.components.v1.html(build_copy_button_html(gaps), height=48, scrolling=False)

    if answered:
        # Native HTML <details> to avoid Streamlit's broken chevron icon.
        # The list of answered questions is plain HTML so the whole block
        # can live inside one st.markdown call.
        rows_html = "".join(
            f'<div style="font-size:0.85rem;color:#64748B;padding:5px 0;'
            f'border-bottom:1px solid #F1F5F9;">'
            f'<span style="color:#1D9E75;margin-right:6px;">✓</span>'
            f'{_clean_str(concept.get("question", ""))}</div>'
            for concept in answered
        )
        st.markdown(
            f'<details class="diq-html-details">'
            f'<summary>Questions the document answered ({len(answered)})</summary>'
            f'<div class="diq-html-details-body">'
            f'{rows_html}'
            f'</div></details>',
            unsafe_allow_html=True,
        )


# ── Section dispatch ─────────────────────────────────────────────────────────

_SECTION_RENDERERS = {
    "diagnosis":    _render_section_diagnosis,
    "medications":  _render_section_medications,
    "appointments": _render_section_appointments,
    "warnings":     _render_section_warning_signs,
    "recovery":     _render_section_recovery,
    "simulator":    _render_section_simulator,
}


# ── Chat widget (fixed right panel, 320px) ──────────────────────────────────

def _render_chat_widget(result: dict) -> None:
    """
    Inject the fixed 320px right-side chat panel into the parent DOM.

    Chat history is persisted in window.parent.sessionStorage keyed by
    the first 20 chars of the pipeline-context base64 — so the thread
    survives tab switches and any other Streamlit rerun within the same
    browser session. On re-injection, loadHistory() replays every
    stored message into the fresh panel so the conversation continues
    seamlessly.

    The widget POSTs to /chat directly from JS — no Python round-trip.

    Args:
        result: PipelineResponse dict. Used for the suggestion chip
                label (primary diagnosis, first 4 words) and encoded
                into the /chat pipeline_context parameter.
    """
    ext = result.get("extraction", {})
    primary_dx = _clean_str(ext.get("primary_diagnosis")) or "your condition"
    # Two-step escape: html.escape() neutralises &, <, >, " for the markup
    # below, then .replace("'", "\\'") protects the surrounding JS string
    # context. _clean_str() already strips any HTML tags from the LLM output.
    dx_short = html.escape(" ".join(primary_dx.split()[:4])).replace("'", "\\'")

    context_b64 = base64.b64encode(
        json.dumps(result, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")

    panel_css = """
      #diq-panel-root * { box-sizing: border-box; }
      #diq-panel-root {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      }

      /* Floating chat panel (popup-style).
         Width is user-adjustable via the left-edge resize handle and the
         maximize toggle; state persists for the browser tab. */
      #diq-chat-panel {
        position: fixed; right: 0; top: 96px;
        width: 340px; height: calc(100vh - 96px);
        min-width: 280px; max-width: 720px;
        background: #fff;
        border-left: 1px solid #E2E8F0;
        box-shadow: -6px 0 16px rgba(15, 23, 42, 0.06);
        display: flex; flex-direction: column;
        z-index: 9999;
      }
      #diq-chat-panel.diq-hidden { display: none; }

      /* Resize handle — invisible 6px strip on the left edge. Cursor
         flips to col-resize so the affordance is clear on hover. */
      #diq-panel-resize {
        position: absolute; left: -3px; top: 0;
        width: 6px; height: 100%;
        cursor: col-resize; background: transparent;
        z-index: 10000;
      }
      #diq-panel-resize:hover { background: rgba(15,110,86,0.15); }
      body.diq-resizing { cursor: col-resize !important; user-select: none; }

      #diq-panel-header {
        background: #0f6e56; color: #fff;
        padding: 12px 10px 12px 14px;
        display: flex; align-items: center;
        flex-shrink: 0;
        gap: 10px;
      }
      #diq-panel-header svg { flex-shrink: 0; }
      #diq-panel-header h4 {
        margin: 0; font-size: 13px; font-weight: 700; flex: 1;
        letter-spacing: 0.01em;
      }
      .diq-panel-iconbtn {
        background: transparent; border: none; color: #ffffff;
        width: 26px; height: 26px; border-radius: 4px;
        display: inline-flex; align-items: center; justify-content: center;
        cursor: pointer; padding: 0;
      }
      .diq-panel-iconbtn:hover { background: rgba(255,255,255,0.18); }

      #diq-panel-chips {
        display: flex; flex-wrap: wrap; gap: 5px;
        padding: 8px 10px 6px;
        border-bottom: 1px solid #F1F5F9;
        flex-shrink: 0;
      }
      .diq-panel-chip {
        background: #CCFBF1; color: #0F766E;
        border: 1px solid #99F6E4; border-radius: 12px;
        padding: 3px 9px; font-size: 11px;
        cursor: pointer; white-space: nowrap;
      }
      .diq-panel-chip:hover { background: #99F6E4; }

      #diq-panel-thread {
        flex: 1; overflow-y: auto;
        padding: 10px 12px;
        display: flex; flex-direction: column; gap: 8px;
      }

      /* Typography normalized: both bubbles share one size / line-height
         so user and AI messages visually match. Markdown <p>/<ul>/<b>
         inside the AI bubble inherit these values, which was the source
         of the earlier "weird sizing" report. */
      .diq-msg-user, .diq-msg-ai {
        font-size: 12px; line-height: 1.4; font-weight: 400;
        padding: 7px 10px; word-break: break-word;
      }
      .diq-msg-user *, .diq-msg-ai * {
        font-size: inherit !important; line-height: inherit !important;
      }
      .diq-msg-user {
        align-self: flex-end; background: #0f6e56; color: #fff;
        border-radius: 12px 12px 2px 12px;
        max-width: 86%;
      }
      .diq-msg-ai {
        align-self: flex-start; background: #F8FAFC; color: #1E293B;
        border: 1px solid #E2E8F0;
        border-radius: 12px 12px 12px 2px;
        max-width: 92%;
      }
      .diq-msg-ai p:first-child { margin-top: 0; }
      .diq-msg-ai p:last-child { margin-bottom: 0; }
      .diq-msg-ai p { margin: 0 0 4px; }
      .diq-msg-ai ul, .diq-msg-ai ol { margin: 4px 0; padding-left: 18px; }
      .diq-msg-ai li { margin-bottom: 2px; }
      .diq-msg-source {
        font-size: 10.5px; color: #94A3B8; margin-top: 4px;
        font-style: italic;
      }
      .diq-msg-thinking {
        align-self: flex-start; color: #94A3B8; font-size: 12px;
        padding: 5px 11px; font-style: italic;
      }

      #diq-panel-input-row {
        display: flex; gap: 6px;
        padding: 8px 10px; border-top: 1px solid #F1F5F9;
        flex-shrink: 0;
      }
      #diq-panel-input {
        flex: 1; border: 1px solid #E2E8F0; border-radius: 8px;
        padding: 7px 10px; font-size: 13px; outline: none;
        font-family: inherit; background: #fff; color: #1E293B;
      }
      #diq-panel-input:focus { border-color: #0f6e56; }
      #diq-panel-send {
        background: #0f6e56; color: #fff; border: none;
        border-radius: 8px; padding: 7px 14px;
        cursor: pointer; font-size: 13px; font-weight: 600;
      }
      #diq-panel-send:disabled { opacity: 0.5; cursor: not-allowed; }

      /* Floating bubble shown when chat is minimized. Click to re-open. */
      #diq-chat-bubble {
        position: fixed; right: 20px; bottom: 20px;
        width: 54px; height: 54px; border-radius: 50%;
        background: #0f6e56; color: #fff;
        display: none; align-items: center; justify-content: center;
        cursor: pointer; z-index: 9999;
        box-shadow: 0 4px 14px rgba(15, 110, 86, 0.35);
        transition: transform 0.15s ease;
      }
      #diq-chat-bubble.diq-visible { display: flex; }
      #diq-chat-bubble:hover { transform: scale(1.06); }

      /* Push the Streamlit main section right so content never slides under
         the chat panel. --diq-chat-padding is set on <html> by syncMainPadding()
         so it persists across React rerenders (inline styles on stMain are wiped
         whenever Streamlit reruns). Default 0px = no padding when minimized. */
      section[data-testid="stMain"] {
        padding-right: var(--diq-chat-padding, 0px) !important;
      }
    """

    panel_body_html = f"""
      <div id="diq-chat-panel">
        <div id="diq-panel-resize" title="Drag to resize"></div>
        <div id="diq-panel-header">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
               stroke="#fff" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          <h4>Ask about your discharge</h4>
          <button id="diq-panel-expand" class="diq-panel-iconbtn"
                  type="button" title="Toggle wide / narrow">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2.4"
                 stroke-linecap="round" stroke-linejoin="round">
              <path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3
                       M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>
            </svg>
          </button>
          <button id="diq-panel-minimize" class="diq-panel-iconbtn"
                  type="button" title="Minimize">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2.4"
                 stroke-linecap="round">
              <path d="M5 12h14"/>
            </svg>
          </button>
        </div>
        <div id="diq-panel-chips">
          <span class="diq-panel-chip">What is {dx_short}?</span>
          <span class="diq-panel-chip">When is my next appointment?</span>
          <span class="diq-panel-chip">What should I not eat?</span>
          <span class="diq-panel-chip">When should I call 911?</span>
        </div>
        <div id="diq-panel-thread"></div>
        <div id="diq-panel-input-row">
          <input id="diq-panel-input" type="text"
                 placeholder="Type your question\u2026" autocomplete="off">
          <button id="diq-panel-send">Send</button>
        </div>
      </div>
      <button id="diq-chat-bubble" type="button" title="Open chat">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none"
             stroke="#fff" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
      </button>
    """

    widget_html = f"""<!DOCTYPE html><html><head>
<script>
(function() {{
  var pdoc = window.parent.document;
  var CHAT_URL = '{_CHAT_URL}';
  var CONTEXT_B64 = '{context_b64}';
  var STORAGE_KEY = 'diq_chat_msgs_' + CONTEXT_B64.slice(0, 20);

  // ── 1. Inject or replace panel in parent DOM ─────────────────────────────
  ['diq-panel-root', 'diq-panel-styles'].forEach(function(id) {{
    var el = pdoc.getElementById(id);
    if (el) el.remove();
  }});

  var style = pdoc.createElement('style');
  style.id = 'diq-panel-styles';
  style.textContent = {json.dumps(panel_css)};
  pdoc.head.appendChild(style);

  var root = pdoc.createElement('div');
  root.id = 'diq-panel-root';
  root.innerHTML = {json.dumps(panel_body_html)};
  pdoc.body.appendChild(root);

  var panel = pdoc.getElementById('diq-chat-panel');
  var bubble = pdoc.getElementById('diq-chat-bubble');

  var WIDTH_KEY = 'diq_chat_width';
  var MIN_KEY = 'diq_chat_minimized';
  var MIN_W = 280, MAX_W = 720, DEFAULT_W = 340;

  function getSavedWidth() {{
    try {{
      var v = parseInt(window.parent.sessionStorage.getItem(WIDTH_KEY), 10);
      if (!isNaN(v) && v >= MIN_W && v <= MAX_W) return v;
    }} catch(e) {{}}
    return DEFAULT_W;
  }}
  function saveWidth(w) {{
    try {{ window.parent.sessionStorage.setItem(WIDTH_KEY, String(w)); }}
    catch(e) {{}}
  }}
  function isMinimized() {{
    try {{ return window.parent.sessionStorage.getItem(MIN_KEY) === '1'; }}
    catch(e) {{ return false; }}
  }}
  function setMinimized(v) {{
    try {{ window.parent.sessionStorage.setItem(MIN_KEY, v ? '1' : '0'); }}
    catch(e) {{}}
  }}

  function syncMainPadding() {{
    // Set --diq-chat-padding on <html> rather than an inline style on stMain.
    // <html> is never replaced by React rerenders, so the value survives every
    // Streamlit rerun; the CSS rule in panel_css reads it via var().
    if (panel && !panel.classList.contains('diq-hidden')) {{
      var w = panel.getBoundingClientRect().width || DEFAULT_W;
      pdoc.documentElement.style.setProperty('--diq-chat-padding', (w + 16) + 'px');
    }} else {{
      pdoc.documentElement.style.setProperty('--diq-chat-padding', '0px');
    }}
  }}

  function applyPanelWidth(w) {{
    if (!panel) return;
    panel.style.width = w + 'px';
    syncMainPadding();
  }}

  function showPanel() {{
    if (panel) panel.classList.remove('diq-hidden');
    if (bubble) bubble.classList.remove('diq-visible');
    setMinimized(false);
    syncMainPadding();
  }}
  function hidePanel() {{
    if (panel) panel.classList.add('diq-hidden');
    if (bubble) bubble.classList.add('diq-visible');
    setMinimized(true);
    syncMainPadding();
  }}

  applyPanelWidth(getSavedWidth());
  if (isMinimized()) {{ hidePanel(); }} else {{ showPanel(); }}

  // Drag-to-resize on the left edge.
  var resizeHandle = pdoc.getElementById('diq-panel-resize');
  if (resizeHandle) {{
    resizeHandle.addEventListener('mousedown', function(e) {{
      e.preventDefault();
      pdoc.body.classList.add('diq-resizing');
      function onMove(ev) {{
        // Panel is right-anchored, so width = viewport - mouseX.
        var w = Math.max(MIN_W, Math.min(MAX_W, window.parent.innerWidth - ev.clientX));
        applyPanelWidth(w);
      }}
      function onUp() {{
        pdoc.body.classList.remove('diq-resizing');
        pdoc.removeEventListener('mousemove', onMove);
        pdoc.removeEventListener('mouseup', onUp);
        saveWidth(panel.getBoundingClientRect().width | 0);
      }}
      pdoc.addEventListener('mousemove', onMove);
      pdoc.addEventListener('mouseup', onUp);
    }});
  }}

  // Minimize button → collapse to floating bubble.
  var minBtn = pdoc.getElementById('diq-panel-minimize');
  if (minBtn) minBtn.addEventListener('click', hidePanel);

  // Expand button → toggle between current width and max width.
  var expandBtn = pdoc.getElementById('diq-panel-expand');
  if (expandBtn) expandBtn.addEventListener('click', function() {{
    var cur = panel.getBoundingClientRect().width;
    var target = cur < (MIN_W + MAX_W) / 2 ? MAX_W : DEFAULT_W;
    applyPanelWidth(target);
    saveWidth(target);
  }});

  // Floating bubble → restore panel.
  if (bubble) bubble.addEventListener('click', showPanel);

  // Keep main-section padding in sync if viewport resizes.
  window.parent.addEventListener('resize', syncMainPadding);

  // ── 2. Helpers querying the PARENT document ──────────────────────────────
  function $p(id) {{ return pdoc.getElementById(id); }}
  function getThread() {{ return $p('diq-panel-thread'); }}
  function getInput()  {{ return $p('diq-panel-input'); }}

  // ── 3. Parse pipeline context ────────────────────────────────────────────
  var pipelineContext = null;
  try {{ pipelineContext = JSON.parse(atob(CONTEXT_B64)); }} catch(e) {{}}

  // ── 4. Session ID — persisted across rerenders ───────────────────────────
  var sessionId = (function() {{
    var key = 'diq_session_id';
    try {{
      var existing = window.parent.sessionStorage.getItem(key);
      if (existing) return existing;
      var id = Math.random().toString(36).slice(2);
      window.parent.sessionStorage.setItem(key, id);
      return id;
    }} catch(e) {{ return Math.random().toString(36).slice(2); }}
  }})();

  function loadHistory() {{
    try {{
      return JSON.parse(window.parent.sessionStorage.getItem(STORAGE_KEY) || '[]');
    }} catch(e) {{ return []; }}
  }}
  function saveHistory(msgs) {{
    try {{ window.parent.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(msgs)); }}
    catch(e) {{}}
  }}

  // ── 5. Lightweight markdown renderer for AI messages ─────────────────────
  function escapeHtml(s) {{
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;')
            .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }}

  function renderInline(s) {{
    return escapeHtml(s)
      .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
      .replace(/\\*(.+?)\\*/g, '<em>$1</em>');
  }}

  function renderMarkdown(text) {{
    var lines = text.split('\\n');
    var html = '';
    var inUl = false;
    var inOl = false;

    function closeList() {{
      if (inUl) {{ html += '</ul>'; inUl = false; }}
      if (inOl) {{ html += '</ol>'; inOl = false; }}
    }}

    lines.forEach(function(line) {{
      var ul = line.match(/^[-*] (.+)/);
      var ol = line.match(/^\\d+\\.\\s+(.+)/);
      var blank = line.trim() === '';

      if (ul) {{
        if (inOl) {{ html += '</ol>'; inOl = false; }}
        if (!inUl) {{ html += '<ul>'; inUl = true; }}
        html += '<li>' + renderInline(ul[1]) + '</li>';
      }} else if (ol) {{
        if (inUl) {{ html += '</ul>'; inUl = false; }}
        if (!inOl) {{ html += '<ol>'; inOl = true; }}
        html += '<li>' + renderInline(ol[1]) + '</li>';
      }} else if (blank) {{
        closeList();
      }} else {{
        closeList();
        html += '<p>' + renderInline(line) + '</p>';
      }}
    }});
    closeList();
    return html;
  }}

  // ── 6. Message rendering ─────────────────────────────────────────────────
  function appendUserMsg(text) {{
    var div = pdoc.createElement('div');
    div.className = 'diq-msg-user';
    div.textContent = text;
    getThread().appendChild(div);
    scrollThread();
  }}

  function appendAiMsg(text, sourcePage, fromDocument) {{
    var wrap = pdoc.createElement('div');
    wrap.className = 'diq-msg-ai';
    wrap.innerHTML = renderMarkdown(text);
    var src = pdoc.createElement('div');
    src.className = 'diq-msg-source';
    // Patient-trust rule: never claim "from your document" for answers the
    // model flagged as general medical knowledge \u2014 the backend signals this
    // via from_document=false. Default to true for older cached entries so
    // pre-upgrade history still renders something sensible.
    if (fromDocument === false) {{
      src.textContent = '\u2014 general medical guidance \u00b7 not from your document';
      src.style.color = '#B45309';
      src.style.fontStyle = 'normal';
    }} else if (sourcePage) {{
      src.textContent = '\u2014 from your document (p.' + sourcePage + ')';
    }} else {{
      src.textContent = '\u2014 from your document';
    }}
    wrap.appendChild(src);
    getThread().appendChild(wrap);
    scrollThread();
  }}

  function appendThinking() {{
    var div = pdoc.createElement('div');
    div.className = 'diq-msg-thinking';
    div.id = 'diq-thinking-indicator';
    div.textContent = 'Thinking\u2026';
    getThread().appendChild(div);
    scrollThread();
  }}

  function scrollThread() {{
    var t = getThread();
    if (t) t.scrollTop = t.scrollHeight;
  }}

  // ── 7. Restore history from sessionStorage ───────────────────────────────
  loadHistory().forEach(function(msg) {{
    if (msg.role === 'user') {{
      appendUserMsg(msg.text);
    }} else {{
      // Legacy entries (saved before the from_document field existed) default
      // to true so old conversations still render with a sensible footer.
      var fd = (msg.fromDocument === false) ? false : true;
      appendAiMsg(msg.text, msg.sourcePage || null, fd);
    }}
  }});

  // ── 8. Send message to POST /chat ────────────────────────────────────────
  async function sendMessage() {{
    var input = getInput();
    var text = input.value.trim();
    if (!text) return;

    var sendBtn = $p('diq-panel-send');
    sendBtn.disabled = true;
    input.value = '';

    appendUserMsg(text);
    var history = loadHistory();
    history.push({{ role: 'user', text: text }});
    saveHistory(history);
    appendThinking();

    try {{
      var resp = await fetch(CHAT_URL, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          message: text,
          session_id: sessionId,
          pipeline_context: pipelineContext || {{}}
        }})
      }});

      var thinkEl = pdoc.getElementById('diq-thinking-indicator');
      if (thinkEl) thinkEl.remove();

      if (!resp.ok) {{
        appendAiMsg('Sorry, I could not reach the assistant. Please try again.', null, true);
      }} else {{
        var data = await resp.json();
        var reply = data.reply || 'No response received.';
        var sourcePage = data.source_page || null;
        // Backend signals when the answer is general medical knowledge rather
        // than grounded in the patient's PDF. Default to true for older
        // backends that don't yet emit the field.
        var fromDocument = (data.from_document === false) ? false : true;
        appendAiMsg(reply, sourcePage, fromDocument);
        history.push({{
          role: 'ai',
          text: reply,
          sourcePage: sourcePage,
          fromDocument: fromDocument,
        }});
        saveHistory(history);
      }}
    }} catch(err) {{
      var thinkEl2 = pdoc.getElementById('diq-thinking-indicator');
      if (thinkEl2) thinkEl2.remove();
      appendAiMsg('Could not reach the DischargeIQ server. Make sure it is running.', null, true);
    }} finally {{
      sendBtn.disabled = false;
    }}
  }}

  // ── 9. Wire up event listeners ───────────────────────────────────────────
  $p('diq-panel-send').addEventListener('click', sendMessage);
  $p('diq-panel-input').addEventListener('keydown', function(e) {{
    if (e.key === 'Enter') sendMessage();
  }});

  pdoc.querySelectorAll('#diq-panel-chips .diq-panel-chip').forEach(function(chip) {{
    chip.addEventListener('click', function() {{
      getInput().value = chip.textContent.trim();
      sendMessage();
    }});
  }});

}})();
</script>
</head><body style="margin:0;padding:0;background:transparent;"></body></html>"""

    st.components.v1.html(widget_html, height=1, scrolling=False)


# ── Landing intro (cinematic) ─────────────────────────────────────────────────


def _landing_intro_html() -> str:
    """
    Return the complete HTML document for the cinematic landing intro.

    Animation timeline (ms relative to script start):
       300  "HELPING" small-caps eyebrow fades in
       850  "patients" rises in
      1250  "understand"
      1650  "everything"
      2050  "the doctor"
      2500  italic teal "just told them."
      4500  phrase block fades out (600 ms)
      4700  logo container fades in; "Discharge" typewriter starts (~90 ms / char)
      ~5510 typewriter completes
      ~5750 "IQ" snaps in; caret hides simultaneously (no caret jump)
      ~6100 subtitle "Your discharge, simplified." fades in
      7400  vignette + skip fade out
      7800  logo fades out (~400 ms)
      8300  dark stage fades to opacity 0 (~700 ms); bg stays dark green
      9100  hidden advance button clicked → Streamlit rerun → upload screen

    Persistence:
      None. Plays on every fresh Streamlit session. Cmd-R allocates a new
      ws session which resets _S_LANDING_DONE → False, so the cinematic
      naturally replays on every reload (matching how product demos are
      typically shown). No browser-storage gating.

    Advance mechanism:
      Locates the hidden Streamlit button rendered by _hidden_click_target
      with sentinel '__diq_landing_done__' and calls .click() on it. The
      click triggers a Streamlit rerun, _S_LANDING_DONE flips to True, and
      the next render reaches _render_upload_screen() instead of this
      iframe.

      tryClick() polls every 100 ms for up to 6 s in case the parent React
      tree hasn't mounted the hidden button yet when advance() fires (a
      real race seen on first load — without retry the iframe was leaving
      the user staring at a blank dark-green page).

    Visual continuity:
      The end-of-cinematic fades the logo then fades the entire dark stage
      to opacity 0. advance() fires once the stage is invisible, so the
      iframe unmount reveals the upload screen without any visible jump.

    Returns:
        Complete <!DOCTYPE html> document. No Python interpolation, so a
        plain triple-quoted string is used (no f-string brace doubling).
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Carlito:ital,wght@0,400;0,700;1,400;1,700&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{
    width:100%;height:100%;overflow:hidden;background:#04342C;
    font-family:Calibri,'Carlito','Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;
    color:#E6EFE9;
  }

  /* Stage — fades to opacity 0 after logo exits, so the dark green
     background is never replaced with white; the upload screen reveals
     beneath it once the iframe is invisible. cubic-bezier is iOS easeOut. */
  #stage{
    position:fixed;inset:0;background:#04342C;
    display:flex;align-items:center;justify-content:center;
    transition:opacity 700ms cubic-bezier(.32,.72,0,1);
  }
  #stage.gone{ opacity:0; pointer-events:none; }

  #vignette{
    position:absolute;inset:0;pointer-events:none;
    background:radial-gradient(ellipse at center,
      rgba(15,110,86,0.22) 0%, rgba(0,0,0,0.0) 55%);
    transition:opacity 700ms cubic-bezier(.32,.72,0,1);
  }
  #vignette.gone{ opacity:0; }

  #skip{
    position:absolute;top:22px;right:24px;
    background:transparent;
    border:1px solid rgba(255,255,255,0.18);
    color:rgba(255,255,255,0.55);
    font-size:11px;font-weight:500;letter-spacing:0.6px;
    text-transform:uppercase;
    padding:6px 14px;border-radius:999px;cursor:pointer;
    transition:color .2s, border-color .2s, opacity .45s ease;
    z-index:5;font-family:Calibri,'Carlito','Segoe UI',sans-serif;
  }
  #skip:hover{
    color:rgba(255,255,255,0.92);
    border-color:rgba(255,255,255,0.42);
  }
  #skip.gone{ opacity:0; pointer-events:none; }

  /* Phrase block ---------------------------------------------------------- */
  #phrase{
    position:relative;text-align:center;
    transition:opacity 600ms cubic-bezier(.32,.72,0,1);
  }
  #phrase.gone{ opacity:0; }

  /* "HELPING" eyebrow — small caps label, intentionally smaller to read as
     a category line rather than a body line. */
  .helping{
    font-family:Calibri,'Carlito','Segoe UI',sans-serif;
    font-size:12px;font-weight:500;letter-spacing:5.5px;
    color:rgba(190,210,200,0.55);
    margin-bottom:24px;
    opacity:0;transform:translateY(6px);
    transition:opacity 700ms cubic-bezier(.32,.72,0,1),
               transform 700ms cubic-bezier(.32,.72,0,1);
  }

  /* Body lines — five lines, all uniform 56px, single line-height, identical
     visual weight (italic uses 600 instead of 500 to compensate for the
     visual shrinkage italic Cormorant renders at the same point size). */
  .line{
    font-family:Calibri,'Carlito','Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;
    font-size:56px;font-weight:500;line-height:1.14;
    letter-spacing:-0.005em;color:#E6EFE9;
    opacity:0;transform:translateY(16px);
    transition:opacity 800ms cubic-bezier(.32,.72,0,1),
               transform 800ms cubic-bezier(.32,.72,0,1);
  }
  .line.italic{
    font-style:italic;
    font-weight:600;
    color:#5DCAA5;
    margin-top:8px;
  }
  .show{ opacity:1 !important; transform:translateY(0) !important; }

  /* Logo block ------------------------------------------------------------ */
  #logo{
    position:absolute;text-align:center;
    opacity:0;transition:opacity 600ms cubic-bezier(.32,.72,0,1);
  }
  #logo.show{ opacity:1; }
  #logo.gone{ opacity:0; }

  /* Flexbox row keeps Discharge | caret | IQ on a shared baseline so the
     caret always sits flush at the right edge of the typed letters,
     regardless of how many letters have been typed so far. */
  .wordmark-row{
    display:flex;align-items:baseline;justify-content:center;
    line-height:1;
  }
  .wordmark{
    font-family:Calibri,'Carlito','Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;
    font-size:78px;font-weight:600;letter-spacing:-1.5px;
    color:#1FA47F;
    display:inline-block;
  }

  /* IQ stays display:none until snap-in. opacity:0 alone wouldn't work
     because the span would still reserve width and push the caret off
     the right edge of "Discharge" while typing. */
  #iq{ display:none; }
  #iq.show{ display:inline-block; }

  /* Caret sits between Discharge and IQ — flush against the typed text. */
  #caret{
    display:inline-block;width:3px;height:0.7em;
    background:#1FA47F;margin:0 2px 0 3px;
    align-self:center;
    animation:blink 720ms step-start infinite;
  }
  #caret.gone{ display:none; }
  @keyframes blink{ 50%{ opacity:0; } }

  .subtitle{
    font-family:Calibri,'Carlito','Segoe UI',sans-serif;
    font-size:12px;font-weight:400;letter-spacing:1.4px;
    color:rgba(190,210,200,0.5);
    margin-top:24px;text-transform:uppercase;
    opacity:0;transition:opacity 800ms cubic-bezier(.32,.72,0,1);
  }
  .subtitle.show{ opacity:1; }
</style>
</head>
<body>
  <div id="stage">
    <div id="vignette"></div>
    <button id="skip" type="button">Skip</button>

    <div id="phrase">
      <div class="helping" id="w-helping">HELPING</div>
      <div class="line"           id="w-1">patients</div>
      <div class="line"           id="w-2">understand</div>
      <div class="line"           id="w-3">everything</div>
      <div class="line"           id="w-4">the doctor</div>
      <div class="line italic"    id="w-5">just told them.</div>
    </div>

    <div id="logo">
      <div class="wordmark-row">
        <span class="wordmark" id="discharge"></span><span id="caret"></span><span class="wordmark" id="iq">IQ</span>
      </div>
      <div class="subtitle" id="subtitle">Your discharge, simplified.</div>
    </div>
  </div>

<script>
(function(){
  var advanced = false;

  // 1. Expand iframe to full viewport + suppress Streamlit chrome ---------
  function expand(){
    var f = window.frameElement;
    if (f) {
      var s = f.style;
      s.position = 'fixed'; s.inset = '0';
      s.width = '100vw'; s.height = '100vh';
      s.zIndex = '9999';
      s.border = 'none'; s.margin = '0'; s.padding = '0';
    }
    try {
      var pdoc = window.parent.document;
      if (!pdoc.getElementById('diq-landing-parent-style')) {
        var el = pdoc.createElement('style');
        el.id = 'diq-landing-parent-style';
        el.textContent =
          'header[data-testid="stHeader"]{display:none!important}' +
          'footer{display:none!important}' +
          'div[data-testid="stDecoration"]{display:none!important}' +
          'section[data-testid="stMain"]{padding:0!important}';
        pdoc.head.appendChild(el);
      }
    } catch(e) {}
  }
  expand();
  window.addEventListener('load', expand);

  // 2. Advance to upload screen via the hidden Streamlit button -----------
  // Polls every 100 ms for up to 6 s in case the parent React tree hasn't
  // mounted the hidden button yet (it hadn't on first load — without this
  // retry the iframe was leaving the user staring at a blank dark page).
  function advance(){
    if (advanced) return;
    advanced = true;
    var attempts = 0;
    function tryClick(){
      try {
        var pdoc = window.parent.document;
        var marker = pdoc.querySelector('span[data-diq-slot="__diq_landing_done__"]');
        if (marker) {
          var slot = marker.closest('div[data-testid="stElementContainer"]');
          if (slot) {
            var next = slot.nextElementSibling;
            if (next) {
              var btn = next.querySelector('button');
              if (btn) { btn.click(); return; }
            }
          }
        }
      } catch(e) {}
      if (++attempts < 60) setTimeout(tryClick, 100);
    }
    tryClick();
  }

  // 3. Skip button binding ------------------------------------------------
  // Logo fades first (400 ms), then the dark stage fades to opacity 0
  // (700 ms), then advance fires. Mirrors the natural completion path.
  function bindSkip(){
    var skip = document.getElementById('skip');
    if (!skip) return;
    skip.addEventListener('click', function(){
      skip.classList.add('gone');
      hide('vignette');
      hide('phrase');
      hide('logo');
      var stage = document.getElementById('stage');
      if (stage) {
        setTimeout(function(){ stage.classList.add('gone'); }, 400);
      }
      setTimeout(advance, 1200);
    });
  }

  // 4. Animation helpers --------------------------------------------------
  function show(id){ var el = document.getElementById(id); if (el) el.classList.add('show'); }
  function hide(id){ var el = document.getElementById(id); if (el) el.classList.add('gone'); }

  function typewriter(id, word, perChar, doneCb){
    var el = document.getElementById(id);
    if (!el) { if (doneCb) doneCb(); return; }
    var i = 0;
    var t = setInterval(function(){
      i += 1;
      el.textContent = word.slice(0, i);
      if (i >= word.length) {
        clearInterval(t);
        if (doneCb) doneCb();
      }
    }, perChar);
  }

  // 5. Animation timeline -------------------------------------------------
  function runTimeline(){
    // Phase A — phrase build (deliberate cadence, 400-450 ms between lines)
    setTimeout(function(){ show('w-helping'); },  300);
    setTimeout(function(){ show('w-1'); },        850);
    setTimeout(function(){ show('w-2'); },       1250);
    setTimeout(function(){ show('w-3'); },       1650);
    setTimeout(function(){ show('w-4'); },       2050);
    setTimeout(function(){ show('w-5'); },       2500);

    // Phase B — phrase fades out (after ~2 s dwell on the full block)
    setTimeout(function(){ hide('phrase'); },    4500);

    // Phase C/D — logo typewriter, IQ snap (caret hides at the same
    // instant so there's no caret-jump artifact), subtitle reveal.
    setTimeout(function(){
      var logo = document.getElementById('logo');
      if (logo) logo.classList.add('show');
      typewriter('discharge', 'Discharge', 90, function(){
        setTimeout(function(){
          show('iq');
          hide('caret');
          setTimeout(function(){ show('subtitle'); }, 350);
        }, 240);
      });
    }, 4700);

    // Phase E — graceful exit. Four beats:
    //   7400  fade decorations (vignette, skip)
    //   7800  logo fades out (~400 ms CSS transition on #logo)
    //   8300  dark stage fades to opacity 0 (~700 ms); bg stays dark green
    //   9100  advance() — stage is invisible, iframe unmount is seamless.
    setTimeout(function(){
      hide('vignette');
      hide('skip');
    },                                            7400);
    setTimeout(function(){
      hide('logo');
    },                                            7800);
    setTimeout(function(){
      var stage = document.getElementById('stage');
      if (stage) stage.classList.add('gone');
    },                                            8300);
    setTimeout(advance,                           9100);
  }

  bindSkip();
  runTimeline();
})();
</script>
</body>
</html>"""


def _render_landing_intro() -> None:
    """
    Render the cinematic landing intro screen.

    Renders a hidden Streamlit button (sentinel '__diq_landing_done__') and
    the full-viewport iframe defined by _landing_intro_html(). The iframe
    JS clicks the hidden button when the animation completes (or when the
    user presses Skip), which flips _S_LANDING_DONE=True and reruns into
    the upload screen.

    Gated by main() — runs once per Streamlit session. Cmd-R allocates a
    fresh session which resets _S_LANDING_DONE, so the cinematic naturally
    replays on every page reload. No sessionStorage gating is used.
    """
    if _hidden_click_target("__diq_landing_done__", key="landing_done_btn"):
        st.session_state[_S_LANDING_DONE] = True
        st.rerun()

    st.components.v1.html(_landing_intro_html(), height=200, scrolling=False)


# ── Upload screen (Design M) ──────────────────────────────────────────────────


def _render_upload_screen() -> None:
    """
    Render the Design M upload page.

    Layout:
      - Custom sticky navbar (DischargeIQ wordmark + disclaimer + dark toggle)
      - Centered hero (badge, 38px heading, italic green line, subtext)
      - 4 step cards in a horizontal row
      - Dashed-border upload zone (icon + text + native file uploader)
      - "Get started →" Streamlit button (outlined when no file, filled when ready)
      - Privacy note

    Dark mode is toggled via a hidden Streamlit button wired to the navbar
    toggle using the .diq-hidden-btn-slot pattern from _inject_global_css().
    Pass 1 of the two-pass loading animation: when "Get started" is clicked,
    PDF bytes are staged in session state, _S_LOADING_SHOWN is set True, and
    st.rerun() flushes the loading card delta to the browser before Pass 2
    blocks on _call_analyze().
    """
    _cleanup_parent_dom()

    dark = st.session_state.get(_S_UPLOAD_DARK, False)

    # ── Color tokens ──────────────────────────────────────────────────────────
    if dark:
        # Project-brand dark theme. Background is a deep green-charcoal
        # tuned to match the project's #0F6E56 / #1D9E75 brand greens
        # without going as saturated as the original #04342C (which over-
        # tinted everything green) or as cool as a blue slate (which
        # clashed with the rest of the UI). Cards and chrome use subtle
        # green-shifted dark tints rather than blue-greys so the whole
        # page reads as one palette family.
        bg             = "#0B1F1A"
        card_bg        = "rgba(15,110,86,0.18)"
        heading_col    = "#F0FDF9"
        italic_col     = "#5DCAA5"
        sub_col        = "rgba(190,225,212,0.78)"
        badge_bg       = "rgba(15,110,86,0.32)"
        badge_text     = "#A7E5CF"
        badge_border   = "rgba(157,225,203,0.40)"
        zone_bg        = "rgba(15,110,86,0.12)"
        zone_border    = "rgba(157,225,203,0.32)"
        nav_border     = "rgba(157,225,203,0.18)"
        card_border    = "rgba(157,225,203,0.20)"
        toggle_icon    = "&#9728;"
        toggle_title   = "Switch to light mode"
    else:
        bg             = "#FAFCFB"
        card_bg        = "#FFFFFF"
        heading_col    = "#0A2A1F"
        italic_col     = "#0F6E56"
        sub_col        = "#475569"
        badge_bg       = "#E6F4EF"
        badge_text     = "#0A5240"
        badge_border   = "#A7D9CB"
        zone_bg        = "#F4FBF8"
        zone_border    = "#6FCFb0"
        nav_border     = "#E2E8F0"
        card_border    = "#DDF0E8"
        toggle_icon    = "&#9679;"
        toggle_title   = "Switch to dark mode"

    # ── Page-level CSS overrides ───────────────────────────────────────────────
    # Override the summary-screen defaults set by _inject_global_css() so the
    # upload page uses white/dark bg and no top padding for the header offset.
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        html, body, .stApp, .stMarkdown, p, div, span, button {{
            font-family: Calibri, 'Carlito', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif !important;
            -webkit-font-smoothing: antialiased;
        }}
        /* Apply the upload-page background to html and body too so the
           viewport never shows Streamlit's default off-white peeking
           below the upload card on tall screens. */
        html, body {{ background: {bg} !important; min-height: 100vh; }}
        .stApp {{ background: {bg} !important; min-height: 100vh; }}
        section[data-testid="stMain"] {{
            padding-top: 0 !important;
            background: {bg} !important;
            min-height: 100vh;
        }}
        .block-container {{
            padding-top: 0 !important;
            padding-bottom: 2rem !important;
            max-width: 900px !important;
            background: {bg} !important;
        }}
        div[data-testid="stDecoration"] {{ display: none !important; }}

        /* ── Hidden file_uploader ────────────────────────────────────────────
           The zone iframe forwards user clicks to the "Browse files" button
           inside this hidden st.file_uploader. Same-origin iframes preserve
           the user-activation gesture so the OS file picker opens reliably.
           Once a file is uploaded Streamlit reruns and Python stages it from
           uploaded.getvalue() — no synthetic React events required.
        */
        div[data-testid="stElementContainer"]:has(.diq-uploader-slot),
        div[data-testid="stElementContainer"]:has(.diq-uploader-slot)
          + div[data-testid="stElementContainer"] {{
            position: fixed !important;
            left: -9999px !important;
            top: 0 !important;
            width: 1px !important;
            height: 1px !important;
            opacity: 0 !important;
            overflow: hidden !important;
            pointer-events: auto !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Hidden dark-mode toggle button ────────────────────────────────────────
    # The _hidden_click_target helper renders a .diq-hidden-btn-slot marker
    # followed by an off-screen Streamlit button. The segmented toggle in the
    # navbar calls diqToggleDark() which finds this button by its data-diq-slot
    # attribute and calls .click() on it — no button-text search, no URL reload.
    if _hidden_click_target("__diq_dark_toggle__", key="dark_toggle"):
        st.session_state[_S_UPLOAD_DARK] = not st.session_state.get(
            _S_UPLOAD_DARK, False
        )
        st.rerun()

    # ── Navbar (rendered via st.components.v1.html so <script> executes) ────────
    # st.markdown() strips <script> tags for security — JS placed there is dead.
    # st.components.v1.html() renders an iframe where scripts execute normally
    # and window.parent.document gives access to the Streamlit DOM above.
    sun_bg          = "#0F6E56" if not dark else "transparent"
    sun_stroke      = "white"   if not dark else "#0F6E56"
    moon_bg         = "#0F6E56" if dark      else "transparent"
    moon_stroke     = "white"   if dark      else "#0F6E56"
    pill_border_col = "#9FD9C8" if not dark  else "rgba(157,225,203,0.4)"
    pill_bg_col     = "#E1F5EE" if not dark  else "rgba(15,110,86,0.3)"
    toggle_title_text = "Switch to light mode" if dark else "Switch to dark mode"

    navbar_html = f"""<!DOCTYPE html><html><head><script>
(function() {{
  function diqToggleDark() {{
    var pdoc = window.parent.document;
    var marker = pdoc.querySelector('span[data-diq-slot="__diq_dark_toggle__"]');
    if (!marker) return;
    var slot = marker.closest('div[data-testid="stElementContainer"]');
    if (!slot) return;
    var btnContainer = slot.nextElementSibling;
    if (!btnContainer) return;
    var btn = btnContainer.querySelector('button');
    if (btn) btn.click();
  }}

  window.addEventListener('load', function() {{
    var sunBtn  = document.getElementById('diq-sun-btn');
    var moonBtn = document.getElementById('diq-moon-btn');
    if (sunBtn)  sunBtn.addEventListener('click',  diqToggleDark);
    if (moonBtn) moonBtn.addEventListener('click', diqToggleDark);
  }});
}})();
</script></head>
<body style="margin:0;padding:0;background:transparent;
             font-family:Calibri,'Carlito','Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;">
<nav style="display:flex;align-items:center;justify-content:space-between;
            padding:14px 24px;border-bottom:1px solid {nav_border};
            background:{bg};box-sizing:border-box;width:100%;">
  <span style="font-size:18px;font-weight:700;color:#0F6E56;letter-spacing:-0.3px;">
    DischargeIQ
  </span>
  <div style="display:flex;align-items:center;gap:10px;">
    <span style="font-size:11px;color:{sub_col};">Patient chatbot · AI gap finder</span>
    <div title="{toggle_title_text}"
         style="display:flex;background:{pill_bg_col};border-radius:8px;
                overflow:hidden;border:0.5px solid {pill_border_col};flex-shrink:0;">
      <div id="diq-sun-btn"
           style="width:28px;height:28px;display:flex;align-items:center;
                  justify-content:center;background:{sun_bg};cursor:pointer;">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
             stroke="{sun_stroke}" stroke-width="2.2" stroke-linecap="round">
          <circle cx="12" cy="12" r="4"/>
          <line x1="12" y1="2"          x2="12" y2="4"/>
          <line x1="12" y1="20"         x2="12" y2="22"/>
          <line x1="4.22" y1="4.22"     x2="5.64" y2="5.64"/>
          <line x1="18.36" y1="18.36"   x2="19.78" y2="19.78"/>
          <line x1="2"    y1="12"       x2="4"    y2="12"/>
          <line x1="20"   y1="12"       x2="22"   y2="12"/>
          <line x1="4.22"  y1="19.78"   x2="5.64"  y2="18.36"/>
          <line x1="18.36" y1="5.64"    x2="19.78" y2="4.22"/>
        </svg>
      </div>
      <div id="diq-moon-btn"
           style="width:28px;height:28px;display:flex;align-items:center;
                  justify-content:center;background:{moon_bg};cursor:pointer;">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
             stroke="{moon_stroke}" stroke-width="2.2" stroke-linecap="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      </div>
    </div>
  </div>
</nav>
</body></html>"""

    st.components.v1.html(navbar_html, height=56, scrolling=False)

    # ── Main content (centered column) ────────────────────────────────────────
    _, main_col, _ = st.columns([1, 8, 1])
    with main_col:

        # One-shot error from a failed analysis run. Stashed by
        # _run_analysis_with_loading._fail() which then triggers a rerun back
        # to this screen. Cleared immediately so it does not re-show on the
        # next interaction.
        upload_err = st.session_state.get(_S_UPLOAD_ERROR)
        if upload_err:
            st.error(upload_err)
            st.session_state[_S_UPLOAD_ERROR] = None

        # Badge — teal pill with subtle left-dot
        st.markdown(
            f"""
            <div style="margin:40px 0 22px;text-align:center;">
              <span style="display:inline-flex;align-items:center;gap:7px;
                           background:{badge_bg};color:{badge_text};
                           border:1px solid {badge_border};border-radius:999px;
                           padding:6px 18px;font-size:12px;font-weight:600;
                           box-shadow:0 1px 6px rgba(15,110,86,0.10);">
                <span style="width:7px;height:7px;border-radius:50%;
                             background:linear-gradient(135deg,#0F6E56,#1D9E75);
                             display:inline-block;flex-shrink:0;"></span>
                AI-powered · plain language · IIT Chicago CS 595
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Heading + subtext — gradient underline on italic line, refined spacing
        st.markdown(
            f"""
            <div style="text-align:center;margin-bottom:32px;">
              <h1 style="font-size:40px;font-weight:800;color:{heading_col};
                         margin:0;line-height:1.15;letter-spacing:-0.02em;">
                Understand everything
              </h1>
              <h1 style="font-size:40px;font-weight:800;font-style:italic;
                         background:linear-gradient(90deg,#0F6E56,#1D9E75 60%,#34D399);
                         -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                         background-clip:text;margin:0;line-height:1.25;
                         letter-spacing:-0.02em;">
                the doctor just told you.
              </h1>
              <p style="font-size:15px;color:{sub_col};margin:14px 0 0;
                        line-height:1.65;max-width:440px;margin-left:auto;margin-right:auto;">
                Upload your discharge PDF. Get plain-language answers.<br>
                Leave the hospital truly ready.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 4 step cards — gradient icon pill, richer shadow, hover lift
        steps = [
            ("01", "Your diagnosis", "In words a friend would use",
             "linear-gradient(135deg,#0F6E56,#1D9E75)"),
            ("02", "Your medications", "What each pill does &amp; why",
             "linear-gradient(135deg,#1D4ED8,#3B82F6)"),
            ("03", "Warning signs", "When to call 911 vs your doctor",
             "linear-gradient(135deg,#DC2626,#F87171)"),
            ("04", "Ask anything", "AI chat from your document",
             "linear-gradient(135deg,#7C3AED,#A78BFA)"),
        ]
        cards_inner = "".join(
            f"""<div style="flex:1;min-width:0;background:{card_bg};
                             border:1px solid {card_border};border-radius:16px;
                             padding:16px 14px;
                             box-shadow:0 1px 3px rgba(0,0,0,0.05),0 4px 14px rgba(0,0,0,0.07);
                             transition:transform 0.18s ease,box-shadow 0.18s ease;"
                  onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 6px 20px rgba(0,0,0,0.11)'"
                  onmouseout="this.style.transform='';this.style.boxShadow='0 1px 3px rgba(0,0,0,0.05),0 4px 14px rgba(0,0,0,0.07)'">
                  <div style="display:inline-flex;align-items:center;justify-content:center;
                               width:28px;height:28px;border-radius:8px;background:{grad};
                               margin-bottom:10px;">
                    <span style="font-size:10px;font-weight:800;color:#fff;">{num}</span>
                  </div>
                  <div style="font-size:13px;font-weight:700;color:{heading_col};
                               margin-bottom:4px;line-height:1.3;">{title}</div>
                  <div style="font-size:11px;color:{sub_col};line-height:1.4;">{sub}</div>
                </div>"""
            for num, title, sub, grad in steps
        )
        st.markdown(
            f'<div style="display:flex;gap:12px;margin-bottom:26px;">{cards_inner}</div>',
            unsafe_allow_html=True,
        )

        # ── Hidden native file_uploader ──────────────────────────────────────
        # Streamlit's file_uploader handles the upload over its own WebSocket
        # channel — far more reliable than synthesising input/change/blur on a
        # hidden text_area. The iframe zone forwards clicks to the "Browse
        # files" button below; once Streamlit receives a file we stage it
        # immediately. The widget key is suffixed with a counter so
        # _reset_session() can force a fresh widget after "Upload new".
        _uploader_counter = st.session_state.get("_diq_uploader_counter", 0)
        _uploader_key = f"diq_uploader_widget_v{_uploader_counter}"
        st.markdown('<span class="diq-uploader-slot"></span>', unsafe_allow_html=True)
        # NOTE: We deliberately do NOT pass `type=["pdf"]` here. Streamlit's
        # built-in type filter shows its rejection message INSIDE the file
        # uploader widget, which we hide off-screen. Letting all files
        # through and validating in Python below means non-PDF uploads
        # surface as a visible st.error() at the top of the page.
        uploaded_file = st.file_uploader(
            "Upload your discharge PDF",
            key=_uploader_key,
            label_visibility="collapsed",
        )

        if uploaded_file is not None:
            uploaded_name = (uploaded_file.name or "").strip()
            uploaded_lower = uploaded_name.lower()
            uploaded_bytes = uploaded_file.getvalue()
            # Belt-and-suspenders type check. Streamlit's `type=["pdf"]`
            # filters at the OS picker, but a determined user can rename a
            # non-PDF or drop one into the picker via "All files". We also
            # peek at the magic bytes ("%PDF-") so a renamed image / docx
            # doesn't make it past this guard.
            magic_ok = uploaded_bytes[:5] == b"%PDF-"
            ext_ok = uploaded_lower.endswith(".pdf")
            if not ext_ok or not magic_ok:
                st.session_state[_S_STAGED_PDF_BYTES] = None
                st.session_state[_S_STAGED_PDF_NAME] = "document.pdf"
                st.session_state[_S_UPLOAD_ERROR] = (
                    "Only PDF files are allowed. The file you uploaded "
                    f"({uploaded_name or 'unknown'}) is not a valid PDF. "
                    "Please choose a .pdf file and try again."
                )
                # Force a fresh widget so the rejected file disappears.
                st.session_state["_diq_uploader_counter"] = _uploader_counter + 1
                st.rerun()
            elif uploaded_file.size > 20 * 1024 * 1024:
                # Enforce the same 20 MB cap the iframe used to enforce
                # client-side. Larger files would still be accepted by the
                # backend (50 MB cap) but chat and PDF embed get sluggish.
                st.session_state[_S_STAGED_PDF_BYTES] = None
                st.session_state[_S_STAGED_PDF_NAME] = "document.pdf"
                st.session_state[_S_UPLOAD_ERROR] = (
                    "That PDF is larger than 20 MB. Please compress it and try again."
                )
                st.session_state["_diq_uploader_counter"] = _uploader_counter + 1
                st.rerun()
            else:
                st.session_state[_S_STAGED_PDF_BYTES] = uploaded_bytes
                st.session_state[_S_STAGED_PDF_NAME] = uploaded_name

        # Pass 1 — clicked by the iframe when the user hits "Get started →".
        if _hidden_click_target("__diq_file_ready__", key="file_ready_btn"):
            staged_bytes = st.session_state.get(_S_STAGED_PDF_BYTES)
            if staged_bytes:
                logger.info(
                    "File staged via st.file_uploader: %s (%d bytes)",
                    st.session_state.get(_S_STAGED_PDF_NAME, "document.pdf"),
                    len(staged_bytes),
                )
                st.session_state[_S_LOADING_SHOWN] = True
                st.rerun()

        # ── Zone iframe ───────────────────────────────────────────────────────
        # Renders the dashed zone (icon+text left, button right) in a single
        # iframe. Clicking the zone .click()s the parent's hidden file_uploader
        # "Browse files" button — same-origin iframes preserve user activation
        # so the OS file picker opens. Once a file is uploaded Streamlit reruns
        # and we re-render the iframe with the staged filename baked in via
        # STAGED_NAME so the title flips to "Ready to analyze". Hitting "Get
        # started →" clicks the hidden __diq_file_ready__ button, which
        # promotes the staged bytes to _S_LOADING_SHOWN and starts Pass 2.
        _staged_bytes = st.session_state.get(_S_STAGED_PDF_BYTES)
        _staged_name = (
            st.session_state.get(_S_STAGED_PDF_NAME, "")
            if _staged_bytes
            else ""
        )
        _staged_name_js = json.dumps(_staged_name)

        zone_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:transparent;font-family:Calibri,'Carlito','Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;}}
#zone{{
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:16px 20px;background:{zone_bg};
  border:2px dashed {zone_border};border-radius:18px;
  cursor:pointer;user-select:none;min-height:82px;
  transition:border-color 0.2s ease,background 0.2s ease;
  box-shadow:0 2px 12px rgba(15,110,86,0.06);
}}
#zone:hover{{
  border-color:#0F6E56;background:rgba(15,110,86,0.04);
}}
.left{{display:flex;align-items:center;gap:14px;flex:1;min-width:0;}}
.badge{{width:42px;height:42px;
  background:linear-gradient(135deg,#0F6E56,#1D9E75);
  border-radius:12px;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;
  box-shadow:0 3px 10px rgba(15,110,86,0.25);}}
.txt{{flex:1;min-width:0;}}
.title{{font-size:14px;font-weight:700;color:{heading_col};
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.sub{{font-size:11.5px;color:{sub_col};margin-top:3px;}}
#gs{{
  flex-shrink:0;padding:11px 24px;
  background:linear-gradient(135deg,#0F6E56,#1D9E75);color:#fff;
  border:none;border-radius:12px;font-size:13px;font-weight:700;
  cursor:pointer;white-space:nowrap;
  box-shadow:0 3px 12px rgba(15,110,86,0.30);
  transition:opacity 0.18s ease,box-shadow 0.18s ease;
}}
#gs:hover{{opacity:0.9;box-shadow:0 5px 18px rgba(15,110,86,0.38);}}
#gs:disabled{{background:{badge_bg};color:#0F6E56;
  border:1.5px solid {zone_border};cursor:default;opacity:.6;
  box-shadow:none;}}
</style>
<script>
(function(){{
  var STAGED_NAME = {_staged_name_js};

  function findUploaderButton(){{
    // Locate the hidden st.file_uploader's "Browse files" button via its
    // sibling marker span. Returns null if the DOM hasn't mounted yet.
    var pdoc = window.parent.document;
    var slot = pdoc.querySelector('.diq-uploader-slot');
    if(!slot) return null;
    var cont = slot.closest('div[data-testid="stElementContainer"]');
    if(!cont) return null;
    var next = cont.nextElementSibling;
    if(!next) return null;
    return next.querySelector('button');
  }}

  function clickReady(){{
    var pdoc = window.parent.document;
    var m = pdoc.querySelector('span[data-diq-slot="__diq_file_ready__"]');
    if(!m) return;
    var slot = m.closest('div[data-testid="stElementContainer"]');
    if(!slot) return;
    var next = slot.nextElementSibling;
    if(!next) return;
    var btn = next.querySelector('button');
    if(btn) btn.click();
  }}

  window.addEventListener('load',function(){{
    var zone = document.getElementById('zone');
    var gs   = document.getElementById('gs');
    var titleEl = document.querySelector('.title');
    var subEl   = document.querySelector('.sub');

    // Reflect the current staged state on first paint so a Streamlit rerun
    // (e.g. after upload) shows the filename without the user having to
    // re-pick the file.
    if(STAGED_NAME){{
      titleEl.textContent = STAGED_NAME;
      subEl.textContent   = 'Ready to analyze · click to change';
      gs.disabled = false;
    }}

    zone.addEventListener('click',function(e){{
      if(gs.contains(e.target)) return;
      var btn = findUploaderButton();
      if(btn) btn.click();
    }});

    gs.addEventListener('click',function(e){{
      e.stopPropagation();
      if(!STAGED_NAME) return;
      gs.textContent = 'Starting…';
      gs.disabled = true;
      clickReady();
    }});
  }});
}})();
</script>
</head>
<body>
<div id="zone">
  <div class="left">
    <div class="badge">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M12 15V3m0 0L8 7m4-4 4 4" stroke="#0F6E56" stroke-width="1.8"
              stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M3 17v2a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-2"
              stroke="#0F6E56" stroke-width="1.8" stroke-linecap="round"/>
      </svg>
    </div>
    <div class="txt">
      <div class="title">Upload your discharge PDF</div>
      <div class="sub">Private &middot; Deleted after your session ends</div>
    </div>
  </div>
  <button id="gs" disabled>Get started &#8594;</button>
</div>
</body>
</html>"""
        # Iframe must be tall enough to show the full dashed rounded border:
        # zone min-height (82) + 2× zone vertical padding (16) + a few px buffer
        # so the bottom row of dashes and the rounded corners aren't clipped.
        st.components.v1.html(zone_html, height=120, scrolling=False)

        # Privacy note
        st.markdown(
            f"""
            <p style="text-align:center;font-size:11px;color:{sub_col};margin-top:14px;">
              &#128274; Your document is never stored beyond your session
            </p>
            """,
            unsafe_allow_html=True,
        )


# ── Analysis runner (Pass 2 of two-pass loading animation) ────────────────────


def _run_analysis_with_loading() -> None:
    """
    Pass 2 of the two-pass loading animation.

    Called by main() when _S_LOADING_SHOWN is True. Re-renders the loading
    card (keeps it visible in the browser while the Python thread blocks) then
    calls _call_analyze() with the PDF bytes staged in session state by Pass 1.

    On success: stores the PipelineResponse in _S_RESULT and reruns to the
    summary screen. On any error: clears _S_LOADING_SHOWN so the upload screen
    is restored and the error message is shown.

    Args: none — reads all inputs from st.session_state.
    """
    # st.components.v1.html() renders in an iframe — scripts execute, no
    # sanitisation issues. The JS inside expands the iframe to full viewport
    # (position:fixed, inset:0) so the animation is a true full-page takeover.
    # height=200 is the pre-expansion fallback; JS overrides it immediately.
    #
    # Mint a session id BEFORE rendering the loading visual so both the
    # iframe (polling /progress/{id}) and the /analyze POST (sending the same
    # id via header) reference the same record. Without this they wouldn't
    # match and the bar would stay indeterminate forever.
    progress_session_id = str(uuid.uuid4())
    progress_url = f"{_API_BASE}/progress/{progress_session_id}"

    placeholder = st.empty()
    with placeholder.container():
        st.components.v1.html(
            _pipeline_loading_visual_html(progress_url),
            height=200,
            scrolling=False,
        )

    pdf_bytes = st.session_state.get(_S_STAGED_PDF_BYTES)
    pdf_name = st.session_state.get(_S_STAGED_PDF_NAME, "document.pdf")

    if not pdf_bytes:
        # Nothing staged — something went wrong in Pass 1; reset gracefully.
        st.session_state[_S_LOADING_SHOWN] = False
        st.rerun()
        return

    logger.info("Pass 2: analyzing '%s' (%d bytes)", pdf_name, len(pdf_bytes))

    def _fail(msg: str) -> None:
        """
        Reset the loading flag, drop staged bytes, stash the error, and rerun
        so the upload screen renders with the error pinned at the top instead
        of stranding the user on a half-empty loading page.
        """
        placeholder.empty()
        st.session_state[_S_LOADING_SHOWN] = False
        st.session_state[_S_STAGED_PDF_BYTES] = None
        st.session_state[_S_UPLOAD_ERROR] = msg
        st.rerun()

    try:
        result = _call_analyze(pdf_bytes, pdf_name, session_id=progress_session_id)
        placeholder.empty()
        st.session_state[_S_RESULT] = result
        st.session_state[_S_PDF_BYTES] = pdf_bytes
        st.session_state[_S_PDF_SESSION_ID] = result.get("pdf_session_id")
        st.session_state[_S_FILE_NAME] = pdf_name
        st.session_state[_S_ACTIVE_TAB] = "diagnosis"
        st.session_state[_S_PENDING_CITATION] = None
        st.session_state[_S_LOADING_SHOWN] = False
        st.session_state[_S_STAGED_PDF_BYTES] = None
        st.session_state[_S_UPLOAD_ERROR] = None
        logger.info("Pipeline complete — status: %s", result.get("pipeline_status", "unknown"))
        st.rerun()
    except requests.exceptions.ConnectionError:
        _fail(
            "Could not reach the DischargeIQ backend. "
            "Start the server with: `uvicorn dischargeiq.main:app --reload`"
        )
    except requests.exceptions.Timeout:
        _fail(
            "The server took too long to respond. Please try again or use a smaller PDF."
        )
    except _AnalyzeError as api_err:
        logger.error(
            "Analyze returned %d for '%s': %s", api_err.status, pdf_name, api_err.message
        )
        if api_err.status == 413:
            _fail("That PDF is too large. The limit is 50 MB. Try compressing it.")
        elif api_err.status == 415:
            _fail("That file doesn't look like a PDF. Please upload a PDF discharge summary.")
        elif api_err.status == 504:
            _fail("Analysis timed out. Try a smaller or clearer PDF.")
        elif api_err.status >= 500:
            _fail("Something went wrong on our end. Please try again.")
        else:
            _fail(f"Upload failed ({api_err.status}). Please try again.")
    except Exception as unexpected_err:
        logger.error("Unexpected error during analysis: %s", unexpected_err)
        _fail("An unexpected error occurred. Please try again.")


# ── Guided tour (Driver.js) ───────────────────────────────────────────────────


def _inject_guided_tour() -> None:
    """
    Inject a Driver.js guided tour into window.parent.document.

    Loads Driver.js v1.3.1 from jsDelivr CDN on first call. Tour auto-starts
    if sessionStorage key 'diq_tour_done' is not set. ESC, X button, and
    overlay click all dismiss correctly via Driver.js internals. Tour shows
    once per browser session; the header "Take tour" button sets
    _S_TOUR_REPLAY which we consume here to wipe the sessionStorage flag
    and force-restart the tour.

    Styling uses two layered sources (see ensureCss() and ensureStyles()):
    the CDN driver.css provides base positioning/arrow geometry, and an
    inline <style> tag injected on top supplies the !important theme rules
    and the explicit display:flex declarations that driver.css v1.3.1 omits
    on the footer and nav-button containers — without that override the
    Next/Back buttons render with zero height (the original bug).
    """
    force_replay = bool(st.session_state.get(_S_TOUR_REPLAY, False))
    if force_replay:
        st.session_state[_S_TOUR_REPLAY] = False
        logger.info("Take Tour: force_replay=True consumed, injecting tour")
    force_replay_literal = "true" if force_replay else "false"

    tour_html = """<!DOCTYPE html><html><head><script>
(function() {
  var pdoc = window.parent.document;
  var win  = window.parent;
  var FORCE_REPLAY = __DIQ_FORCE_REPLAY__;

  function log() {
    try { console.log.apply(console, ['[diq tour]'].concat([].slice.call(arguments))); }
    catch(e) {}
  }
  log('iframe IIFE running, FORCE_REPLAY=' + FORCE_REPLAY);

  if (FORCE_REPLAY) {
    try { win.sessionStorage.removeItem('diq_tour_done'); } catch(e) {}
  }

  try {
    if (!FORCE_REPLAY && win.sessionStorage.getItem('diq_tour_done') === '1') {
      log('skip — sessionStorage flag set, FORCE_REPLAY=false');
      return;
    }
  } catch(e) {}

  // ── CSS (two layers, both idempotent) ────────────────────────────────────
  // Layer 1 — ensureCss(): loads the CDN driver.css which provides the
  //   critical base rules Driver.js needs to position the popover correctly
  //   (position:fixed, z-index, arrow geometry, stage highlight).  Without
  //   this the popover renders as an invisible collapsed element even though
  //   the dark overlay appears (overlay position is set by JS inline styles).
  // Layer 2 — ensureStyles(): applied after driver.css so our !important
  //   rules win on theme properties.  This layer also adds the footer and
  //   nav-button display:flex rules that driver.css v1.3.1 omits, which was
  //   the original cause of the missing Next/Back buttons.
  function ensureCss() {
    if (pdoc.getElementById('diq-driver-css')) return;
    var link = pdoc.createElement('link');
    link.id  = 'diq-driver-css';
    link.rel = 'stylesheet';
    link.href = 'https://cdn.jsdelivr.net/npm/driver.js@1.3.1/dist/driver.css';
    pdoc.head.appendChild(link);
  }

  function ensureStyles() {
    if (pdoc.getElementById('diq-driver-styles')) return;
    var style = pdoc.createElement('style');
    style.id = 'diq-driver-styles';
    style.textContent = [
      // Overlay colour — overrides driver.css default black
      '.driver-overlay{background:rgba(4,52,44,0.75)!important;}',

      // Popover theme
      '.driver-popover{background:#fff!important;border-radius:16px!important;',
      'border:1.5px solid #9FD9C8!important;',
      'box-shadow:0 12px 40px rgba(4,52,44,0.22)!important;',
      'padding:20px 22px!important;max-width:320px!important;min-width:240px!important;',
      'box-sizing:border-box!important;',
      'font-family:Calibri,"Carlito","Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif!important;}',

      // Header (title + close side-by-side)
      '.driver-popover-header{display:flex!important;align-items:flex-start!important;',
      'justify-content:space-between!important;gap:8px!important;margin-bottom:8px!important;}',

      // Title
      '.driver-popover-title{font-size:15px!important;font-weight:700!important;',
      'color:#0A2A1F!important;line-height:1.4!important;flex:1!important;',
      'margin:0!important;padding:0!important;}',

      // Close button
      '.driver-popover-close-btn{background:none!important;border:none!important;',
      'cursor:pointer!important;font-size:18px!important;color:#94A3B8!important;',
      'padding:0!important;line-height:1!important;flex-shrink:0!important;}',
      '.driver-popover-close-btn:hover{color:#0A2A1F!important;}',

      // Description
      '.driver-popover-description{font-size:13px!important;color:#64748B!important;',
      'line-height:1.6!important;margin:0!important;padding:0!important;}',

      // Footer — display:flex was absent from driver.css v1.3.1, causing
      // the navigation buttons to render with zero height (invisible).
      '.driver-popover-footer{display:flex!important;align-items:center!important;',
      'justify-content:space-between!important;margin-top:14px!important;gap:8px!important;}',

      // Progress text ("Step 2 of 9") — nowrap keeps it on one line
      '.driver-popover-progress-text{font-size:11px!important;color:#0F6E56!important;',
      'font-weight:500!important;flex:1!important;white-space:nowrap!important;}',

      // Nav button container — also requires explicit flex
      '.driver-popover-navigation-btns{display:flex!important;align-items:center!important;',
      'gap:6px!important;flex-shrink:0!important;}',

      // Back button — font-size:0 hides ALL text Driver.js writes (including
      // the "← Previous" flash during step transitions). The ::after pseudo-
      // element shows our label instantly via CSS, with no JS timing dependency.
      '.driver-popover-prev-btn{background:transparent!important;',
      'border:none!important;font-size:0!important;cursor:pointer!important;',
      'padding:7px 12px!important;border-radius:7px!important;',
      'display:inline-flex!important;align-items:center!important;}',
      '.driver-popover-prev-btn:hover{background:#F1F5F9!important;}',
      '.driver-popover-prev-btn::after{content:"Back"!important;',
      'font-size:12px!important;color:#64748B!important;',
      'font-family:Calibri,"Carlito","Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif!important;',
      'font-weight:400!important;}',

      // Next / Done button — same font-size:0 + ::after trick.
      // JS sets data-diq-done on the last step so CSS can switch "Next"→"Done".
      '.driver-popover-next-btn{background:#0F6E56!important;',
      'border:none!important;border-radius:8px!important;padding:7px 16px!important;',
      'font-size:0!important;cursor:pointer!important;',
      'display:inline-flex!important;align-items:center!important;}',
      '.driver-popover-next-btn:hover{background:#085041!important;}',
      '.driver-popover-next-btn::after{content:"Next"!important;',
      'font-size:12px!important;color:#fff!important;',
      'font-family:Calibri,"Carlito","Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif!important;',
      'font-weight:500!important;',
      '-webkit-font-smoothing:antialiased!important;',
      '-moz-osx-font-smoothing:grayscale!important;}',
      '.driver-popover-next-btn[data-diq-done]::after{content:"Done"!important;}',

      // Disabled state (first/last step)
      '.driver-popover-btn-disabled{opacity:0.35!important;pointer-events:none!important;}',

      // Responsive width — never overflow narrow viewports
      '.driver-popover{max-width:min(320px,calc(100vw - 32px))!important;}',

      // Welcome step: CSS-centered so it stays put on zoom/resize.
      // Driver.js sets top/left as inline px values calculated at startup;
      // these !important rules override those inline values so the floating
      // (anchor-less) popover is always viewport-centered regardless of zoom.
      '.driver-popover.diq-welcome-popover{',
      'top:50%!important;left:50%!important;',
      'transform:translate(-50%,-50%)!important;}',
    ].join('');
    pdoc.head.appendChild(style);
  }

  function driverLoaded() {
    return !!(
      (win.driver && win.driver.js && typeof win.driver.js.driver === 'function') ||
      (win.driver && typeof win.driver === 'object' && typeof win.driver.driver === 'function') ||
      (typeof win.driver === 'function') ||
      (win.Driver && typeof win.Driver === 'function')
    );
  }

  function ensureDriverLoaded(cb) {
    if (driverLoaded()) {
      log('reusing already-loaded library');
      return cb();
    }
    if (pdoc.getElementById('diq-driver-script')) {
      log('script tag exists, polling for window.driver');
      var t = setInterval(function() {
        if (driverLoaded()) { clearInterval(t); cb(); }
      }, 80);
      setTimeout(function() { clearInterval(t); }, 6000);
      return;
    }
    log('first load — injecting script');
    var script = pdoc.createElement('script');
    script.id  = 'diq-driver-script';
    script.src = 'https://cdn.jsdelivr.net/npm/driver.js@1.3.1/dist/driver.js.iife.js';
    script.onload = cb;
    pdoc.head.appendChild(script);
  }

  function markDone() {
    try { win.sessionStorage.setItem('diq_tour_done', '1'); } catch(e) {}
  }

  ensureCss();
  ensureStyles();
  log('css injected; waiting 700ms for tab bar and chat panel to mount');
  setTimeout(function() {
    log('delay done; calling ensureDriverLoaded');
    ensureDriverLoaded(function() {
      log('driver ready; starting tour');
      startTour();
    });
  }, 700);

  function startTour() {
    log('startTour() entered; resolving driver global');
    var driverFn = null;
    if (win.driver && win.driver.js && typeof win.driver.js.driver === 'function') {
      driverFn = win.driver.js.driver;
      log('driver resolved via win.driver.js.driver');
    } else if (win.driver && typeof win.driver === 'object' && typeof win.driver.driver === 'function') {
      driverFn = win.driver.driver;
      log('driver resolved via win.driver.driver');
    } else if (typeof win.driver === 'function') {
      driverFn = win.driver;
      log('driver resolved via win.driver');
    } else if (win.Driver && typeof win.Driver === 'function') {
      driverFn = win.Driver;
      log('driver resolved via win.Driver');
    }
    if (!driverFn) {
      console.error('[diq tour] giving up — driver function not found on window');
      return;
    }

    var steps = buildSteps(pdoc);
    log('built ' + steps.length + ' visible steps');
    if (!steps.length) {
      console.error('[diq tour] no visible steps — dropping tour');
      return;
    }

    // driverObj declared first so the resize closure can reference it.
    var driverObj = null;

    // Refresh Driver.js positioning when the viewport changes (zoom / resize).
    function onResize() {
      try {
        if (driverObj && typeof driverObj.refresh === 'function') {
          driverObj.refresh();
        }
      } catch(e) {}
    }

    driverObj = driverFn({
      animate:              true,
      smoothScroll:         true,
      allowClose:           true,
      overlayClickBehavior: 'close',
      showProgress:         true,
      progressText:         'Step {{current}} of {{total}}',
      showButtons:          ['next', 'previous', 'close'],
      // Button labels are now rendered by CSS ::after (immune to Driver.js
      // text writes). onHighlighted only needs to toggle data-diq-done on
      // the last step so the CSS switches "Next" → "Done".
      onHighlighted: function(element, step, opts) {
        var total  = (opts && opts.config && opts.config.steps) ? opts.config.steps.length : 0;
        var idx    = (opts && opts.state && typeof opts.state.activeIndex === 'number')
                      ? opts.state.activeIndex : -1;
        var isLast = total > 0 && idx === total - 1;
        var nextBtn = pdoc.querySelector('.driver-popover-next-btn');
        if (nextBtn) {
          if (isLast) nextBtn.setAttribute('data-diq-done', '');
          else        nextBtn.removeAttribute('data-diq-done');
        }
      },
      onDestroyed: function() {
        markDone();
        win.removeEventListener('resize', onResize);
      },
      steps: steps
    });

    win.addEventListener('resize', onResize);
    driverObj.drive();
  }

  function buildSteps(pdoc) {
    // Steps are filtered at runtime so Driver.js never throws on a missing
    // element (e.g. chat panel not yet mounted).  Steps without an element
    // are always included (they show as centered floating popovers).
    function elementExists(sel) {
      try { return !!pdoc.querySelector(sel); } catch(e) { return false; }
    }

    var steps = [
      // ── Welcome ──────────────────────────────────────────────────────────
      {
        popover: {
          title:        'Welcome to DischargeIQ',
          description:  'Your discharge results are ready. Let us walk you through each section.',
          align:        'center',
          popoverClass: 'diq-welcome-popover'
        }
      },

      // ── Six tabs, one by one ─────────────────────────────────────────────
      {
        element: '#diq-tab-diagnosis',
        popover: {
          title:       'What happened',
          description: 'A plain-English explanation of your diagnosis — no medical jargon.',
          side:        'bottom',
          align:       'start'
        }
      },
      {
        element: '#diq-tab-medications',
        popover: {
          title:       'Medications',
          description: 'What each medicine is for, your dose, and how long to take it.',
          side:        'bottom',
          align:       'start'
        }
      },
      {
        element: '#diq-tab-appointments',
        popover: {
          title:       'Appointments',
          description: 'Your upcoming follow-up visits, sorted by date so nothing gets missed.',
          side:        'bottom',
          align:       'start'
        }
      },
      {
        element: '#diq-tab-warnings',
        popover: {
          title:       'Warning signs',
          description: 'Three clear levels: when to call your doctor, go to urgent care, or call 911.',
          side:        'bottom',
          align:       'start'
        }
      },
      {
        element: '#diq-tab-recovery',
        popover: {
          title:       'Recovery',
          description: 'Your week-by-week plan for getting back to normal life.',
          side:        'bottom',
          align:       'start'
        }
      },
      {
        element: '#diq-tab-simulator',
        popover: {
          title:       'AI Review',
          description: 'Questions your document may not fully answer — bring these to your care team.',
          side:        'bottom',
          align:       'end'
        }
      },

      // ── Chat panel ───────────────────────────────────────────────────────
      {
        element: '#diq-chat-panel',
        popover: {
          title:       'Chat — ask anything',
          description: 'Type any question about your discharge and get an answer grounded in your document.',
          side:        'left',
          align:       'start'
        }
      },

      // ── Source PDF ───────────────────────────────────────────────────────
      {
        element: '#diq-view-pdf-btn',
        popover: {
          title:       'View your original document',
          description: 'Every fact links back to the PDF. Click any page reference to verify the source.',
          side:        'bottom',
          align:       'end'
        }
      }
    ];

    return steps.filter(function(s) {
      return !s.element || elementExists(s.element);
    });
  }

})();
</script></head><body></body></html>"""

    tour_html = tour_html.replace("__DIQ_FORCE_REPLAY__", force_replay_literal)
    st.components.v1.html(tour_html, height=1, scrolling=False)


# ── Summary screen ────────────────────────────────────────────────────────────

def _inject_beforeunload_warning() -> None:
    """
    Inject a beforeunload listener into window.parent so the browser
    shows its native confirmation dialog when the user tries to refresh
    or close the tab while analysis results are visible.

    Modern browsers do not allow custom dialog text — they show their
    own message ("Changes you made may not be saved" in Chrome, similar
    in Firefox and Safari). The __diqBeforeUnloadWired flag prevents
    double-registration across Streamlit reruns.
    """
    st.components.v1.html(
        """<!DOCTYPE html><html><head><script>
(function() {
  var win = window.parent;
  if (win.__diqBeforeUnloadWired) return;
  win.__diqBeforeUnloadWired = true;
  win.addEventListener('beforeunload', function(e) {
    e.preventDefault();
    e.returnValue = '';
  });
})();
</script></head><body></body></html>""",
        height=1,
        scrolling=False,
    )


def _render_summary_screen() -> None:
    """
    Render the post-analysis view: app header, tab bar, active section,
    optional PDF modal, chat panel.

    Only the section matching _S_ACTIVE_TAB is rendered — tab switches
    trigger a rerun and re-enter this function with the new key. If a
    citation chip (or the header "View original document" link) was
    just clicked, _S_PENDING_CITATION holds the target page; the modal
    is injected and the pending state cleared so it will not re-open on
    subsequent reruns (e.g. when the user changes tabs after closing
    the modal).
    """
    result = st.session_state[_S_RESULT]
    active_tab = st.session_state[_S_ACTIVE_TAB]
    pdf_session_id = st.session_state[_S_PDF_SESSION_ID]

    _inject_beforeunload_warning()

    _render_app_header(result)

    _dl_a, _dl_b = st.columns([3, 1])
    with _dl_b:
        try:
            _pdf_blob = _build_summary_pdf_bytes(result)
            st.download_button(
                label="Download summary (PDF)",
                data=_pdf_blob,
                file_name="dischargeiq_plain_language_summary.pdf",
                mime="application/pdf",
                key="download_summary_pdf",
                help="Take-home plain-language summary (not a legal medical record).",
            )
        except Exception as pdf_err:
            logger.warning("Summary PDF build failed: %s", pdf_err)

    _render_tab_bar(active_tab)

    # Dispatch to the active tab's section renderer — only one section
    # renders per run.
    renderer = _SECTION_RENDERERS.get(active_tab, _render_section_diagnosis)
    renderer(result)

    # One-shot PDF modal. Consume the pending state so the modal does
    # not re-open on the next rerun (e.g. tab switch after user closed it).
    pending = st.session_state[_S_PENDING_CITATION]
    if pending:
        _raw_pdf = st.session_state.get(_S_PDF_BYTES)
        _pdf_for_modal = (
            bytes(_raw_pdf)
            if isinstance(_raw_pdf, (bytes, bytearray))
            else None
        )
        _inject_pdf_modal(
            pdf_session_id,
            int(pending.get("page", 1) or 1),
            _pdf_for_modal,
        )
        st.session_state[_S_PENDING_CITATION] = None

    # Chat panel — injected last so it sits above earlier components.
    _render_chat_widget(result)

    # Guided tour — injected after all DOM elements are in place so
    # Driver.js can find the tab bar and chat panel on the first run.
    _inject_guided_tour()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """
    Main entry point for the Streamlit app.

    Routes between four states:
      0. Landing intro    — first visit each tab session; cinematic plays
                            once then advances to the upload screen.
      1. Summary screen   — result is in session state (_S_RESULT is set).
      2. Loading Pass 2   — _S_LOADING_SHOWN is True; bytes are staged and the
                            two-pass animation runner blocks on _call_analyze().
      3. Upload screen    — no result and no pending analysis; show Design M.

    Called at module level because Streamlit re-executes the file on every
    rerender.
    """
    # One-shot cleanup: clears window.parent.sessionStorage and any
    # stale injected DOM nodes on fresh page load (survives Cmd-R).
    # No-op on subsequent reruns within the same Streamlit session.
    _clear_browser_session_on_fresh_load()

    _inject_global_css()

    # Cinematic landing intro — runs in front of the upload screen the first
    # time a Streamlit session is seen. _S_LANDING_DONE resets when Streamlit
    # allocates a new ws session (e.g. on Cmd-R), but the iframe checks
    # window.sessionStorage['_diq_intro_seen'] and short-circuits if that
    # flag is set, so the animation only actually plays on a true new tab.
    if not st.session_state.get(_S_LANDING_DONE, False):
        _render_landing_intro()
        return  # nothing else renders while the intro is on screen

    if st.session_state[_S_RESULT] is not None:
        _render_summary_screen()
    elif st.session_state.get(_S_LOADING_SHOWN, False):
        _run_analysis_with_loading()
        return  # nothing else renders during loading pass
    else:
        _render_upload_screen()


main()
