"""
DischargeIQ Streamlit frontend.

Layout (post-redesign):
  - Teal sticky app header injected into window.parent.document.body
  - Horizontal tab bar (5 tabs) injected just below the header
  - Active section content — only the selected tab's section renders
  - Fixed right-side chat panel (320px) injected into the parent DOM
  - PDF viewer appears as a full-screen modal overlay, opened when a
    citation chip or the header "View original document" link is clicked

All three persistent UI elements (header, tab bar, chat panel) live in
window.parent.document so they survive Streamlit reruns and sit above
the Streamlit main section. State transitions are routed through
hidden Streamlit buttons whose clicks are forwarded from the visible
parent-DOM UI by JS .click(), preserving Streamlit's native button
state-management semantics.

Depends on: streamlit, requests, dischargeiq.utils.logger.
Backend must be running at API_BASE_URL (default http://localhost:8000).
"""

import base64
import json
import logging
import os
import re

import requests
import streamlit as st
from dotenv import load_dotenv

from dischargeiq.utils.logger import configure_logging

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
]

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
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default


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
        /* Page background */
        .stApp { background: #f8f9fa; }
        .block-container {
            padding-top: 0.5rem !important;
            padding-bottom: 1rem !important;
            max-width: 100% !important;
        }

        /* Hide Streamlit's native top toolbar ("Deploy" button etc.) so
           our teal app header is not covered by it. The native toolbar
           sits at a higher z-index than our injected #diq-app-header. */
        header[data-testid="stHeader"] { display: none !important; }

        /* Clear vertical space for the 56px teal app header + ~40px tab
           bar that live outside stMain in window.parent.document. */
        section[data-testid="stMain"] { padding-top: 104px !important; }

        /* Remove Streamlit's default top padding on columns */
        [data-testid="column"] { padding: 0 8px; }

        /* Medication card */
        .diq-med-card {
            background: #fff;
            border-radius: 8px;
            border-left: 4px solid #6366F1;
            padding: 12px 16px;
            margin-bottom: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }

        /* Appointment row */
        .diq-appt-row {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 10px 0;
            border-bottom: 1px solid #E5E7EB;
        }
        .diq-appt-dot {
            width: 10px; height: 10px;
            border-radius: 50%;
            background: #1D9E75;
            flex-shrink: 0;
            margin-top: 5px;
        }

        /* Warning card */
        .diq-warning-card {
            background: #FCEBEB;
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 8px;
        }
        .diq-flag-row {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 6px 0;
        }
        .diq-flag-dot {
            width: 10px; height: 10px;
            border-radius: 50%;
            background: #C0392B;
            flex-shrink: 0;
            margin-top: 5px;
        }

        /* Section title */
        .diq-section-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: #1E293B;
            letter-spacing: 0.01em;
            margin: 14px 0 12px;
            padding-bottom: 5px;
            border-bottom: 2px solid #E2E8F0;
        }

        /* Medication status badge */
        .diq-badge {
            display: inline-block;
            padding: 2px 9px;
            border-radius: 10px;
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            color: #fff;
        }

        /* Changed banner */
        .diq-changed-banner {
            background: #FEF3C7;
            color: #92400E;
            border-radius: 4px;
            padding: 3px 8px;
            font-size: 0.75rem;
            margin-top: 5px;
            display: inline-block;
        }

        /* Secondary-diagnosis pills */
        .diq-dx-pill {
            display: inline-block;
            background: #f1f5f9; color: #475569;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 10px;
            margin: 2px;
        }

        /* Citation chips — teal to signal "linked to your document" */
        button[data-testid="baseButton-secondary"] {
            padding: 2px 8px !important;
            font-size: 0.7rem !important;
            border-radius: 4px !important;
            background: #CCFBF1 !important;
            color: #0F766E !important;
            border: 1px solid #99F6E4 !important;
        }
        button[data-testid="baseButton-secondary"]:hover {
            background: #99F6E4 !important;
        }

        /* Recovery section */
        .diq-recovery-col { font-size: 0.9rem; color: #334155; line-height: 1.8; }
        .diq-discharge-cond {
            background: #F1F5F9;
            border-radius: 6px;
            padding: 8px 14px;
            font-size: 0.85rem;
            color: #64748B;
            margin-top: 10px;
        }

        /* Hidden click-target buttons — used by _hidden_click_target().
           Each hidden button is preceded by a <span class="diq-hidden-btn-slot">
           marker; the adjacent-sibling :has() rule takes BOTH containers out
           of the flex flow entirely (position: absolute) so the parent
           stVerticalBlock's gap between children does not accumulate phantom
           vertical space above the visible content. The button remains
           clickable from JS via .click(). */
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
        /* The button itself must still receive .click() from JS even though
           it lives off-screen, so leave pointer-events enabled. */
        div[data-testid="stElementContainer"]:has(.diq-hidden-btn-slot)
          + div[data-testid="stElementContainer"] {
            pointer-events: auto !important;
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


def _call_analyze(pdf_bytes: bytes, filename: str) -> dict:
    """
    POST the uploaded PDF to the FastAPI /analyze endpoint.

    Args:
        pdf_bytes: Raw bytes of the uploaded file.
        filename:  Original filename for the multipart form field.

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
    response = requests.post(
        _ANALYZE_URL,
        files={"file": (filename, pdf_bytes, "application/pdf")},
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

    Falls back to the original string if parsing fails, so malformed
    dates from the LLM are still shown rather than silently dropped.

    Args:
        iso_date: Date string, e.g. "2026-03-15" or None.

    Returns:
        str: Human-readable date, e.g. "March 15, 2026", or "Date not specified".
    """
    if not iso_date:
        return "Date not specified"
    try:
        from datetime import datetime
        dt = datetime.strptime(iso_date.strip(), "%Y-%m-%d")
        return dt.strftime("%B %-d, %Y")
    except ValueError:
        return iso_date


def _strip_html_tags(text: str) -> str:
    """
    Remove all HTML tags from a string and return clean plain text.

    Args:
        text: Input string that may contain HTML tags.

    Returns:
        str: Plain text with all HTML tags stripped and whitespace trimmed.
    """
    return re.sub(r"<[^>]+>", "", text).strip()


def _clean_str(value: object) -> str:
    """
    Coerce any value to a plain-text string with HTML tags stripped.

    Applied to every LLM-sourced string before it is embedded inside a
    Streamlit unsafe_allow_html=True markdown block so that stray HTML
    markup in the model output cannot break layout or render as visible
    tag text. None, empty strings, and non-string values all return "".

    Args:
        value: Any value from an extraction / agent dict.

    Returns:
        str: Stripped plain-text representation, or "" if falsy.
    """
    if value is None or value == "":
        return ""
    return _strip_html_tags(str(value))


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
    Render a small teal citation chip labelled "p.N".

    On click, stores a pending-citation record in session state so the
    next rerun injects the PDF modal overlay at the cited page. The
    record is cleared immediately after injection to prevent the modal
    from re-opening on subsequent reruns.

    Args:
        page:        1-indexed page number from the source span.
        source_text: Verbatim quote stored on the pending citation.
        key_suffix:  Unique string suffix for the Streamlit widget key.

    Returns:
        bool: True if the button was clicked in this run.
    """
    clicked = st.button(f"p.{page}", key=f"cite_{key_suffix}", type="secondary")
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
    upload_sentinel = "__diq_upload_new_hidden__"
    view_pdf_sentinel = "__diq_view_pdf_hidden__"

    # Hidden click-target buttons. These own the state changes.
    if _hidden_click_target(upload_sentinel, key="upload_new"):
        _reset_session()
        st.rerun()

    if _hidden_click_target(view_pdf_sentinel, key="view_pdf_link"):
        st.session_state[_S_PENDING_CITATION] = {"page": 1, "text": ""}
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

  function clickHiddenBtn(label) {{
    var marker = pdoc.querySelector(
      'span[data-diq-slot="' + label + '"]'
    );
    if (!marker) return;
    var markerContainer = marker.closest(
      'div[data-testid="stElementContainer"]'
    );
    if (!markerContainer) return;
    var btnContainer = markerContainer.nextElementSibling;
    if (!btnContainer) return;
    var btn = btnContainer.querySelector('button');
    if (btn) btn.click();
  }}

  var upBtn = pdoc.getElementById('diq-upload-new-btn');
  if (upBtn) upBtn.addEventListener('click', function() {{
    clickHiddenBtn({json.dumps(upload_sentinel)});
  }});

  var viewBtn = pdoc.getElementById('diq-view-pdf-btn');
  if (viewBtn) viewBtn.addEventListener('click', function() {{
    clickHiddenBtn({json.dumps(view_pdf_sentinel)});
  }});
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
        f'<button class="diq-tab{" active" if k == active_tab else ""}" '
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

  function clickHiddenBtn(label) {{
    var marker = pdoc.querySelector(
      'span[data-diq-slot="' + label + '"]'
    );
    if (!marker) return;
    var markerContainer = marker.closest(
      'div[data-testid="stElementContainer"]'
    );
    if (!markerContainer) return;
    var btnContainer = markerContainer.nextElementSibling;
    if (!btnContainer) return;
    var btn = btnContainer.querySelector('button');
    if (btn) btn.click();
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

def _inject_pdf_modal(pdf_session_id: str | None, page: int) -> None:
    """
    Inject a full-screen PDF modal into window.parent.document.body.

    Called one-shot by _render_summary_screen when _S_PENDING_CITATION
    is set (either by a [p.N] chip click or the header "View original
    document" link). The pending state is consumed after this call so
    the modal does not re-inject on subsequent reruns.

    Args:
        pdf_session_id: UUID from the /analyze response used to build
                        the iframe src. If None, a warning replaces the
                        modal injection.
        page:           1-indexed page number to open the PDF at.
    """
    if not pdf_session_id:
        st.warning("PDF not available for this session — please re-upload the document.")
        return

    iframe_src = f"{_API_BASE}/pdf/{pdf_session_id}#page={page}"

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
          <iframe id="diq-pdf-modal-iframe" src="{iframe_src}"></iframe>
        </div>
      </div>
    """

    injection_html = f"""<!DOCTYPE html><html><head><script>
(function() {{
  var pdoc = window.parent.document;

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

  function closeModal() {{
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
    explanation = _clean_str(result.get("diagnosis_explanation", ""))
    source = ext.get("primary_diagnosis_source")
    secondary = ext.get("secondary_diagnoses", [])

    st.markdown(
        '<div class="diq-section-title">What Happened to You</div>',
        unsafe_allow_html=True,
    )

    if explanation:
        # Agent 2 emits markdown (headers wrapped in **bold**, bullet lists).
        # Passing the text directly to st.markdown() lets Streamlit's
        # CommonMark parser render it. Do NOT wrap the output in a raw
        # <div> with unsafe_allow_html=True — CommonMark does not parse
        # markdown inside block-level HTML, so **bold** would come through
        # as literal asterisks.
        st.markdown(explanation)
    else:
        st.caption("Explanation not available.")

    chip_col, fk_col = st.columns([1, 4])
    with chip_col:
        if source and source.get("page"):
            _citation_button(
                source["page"],
                source.get("text", ""),
                key_suffix="dx",
            )

    with fk_col:
        fk_scores = result.get("fk_scores", {})
        agent2_fk = fk_scores.get("agent2", {})
        if agent2_fk:
            grade = agent2_fk.get("fk_grade", "—")
            passes = agent2_fk.get("passes", False)
            color = "#22C55E" if passes else "#EF4444"
            st.markdown(
                f'<span style="font-size:0.75rem;color:{color};">'
                f'Reading level: grade {grade}</span>',
                unsafe_allow_html=True,
            )

    if secondary:
        pills_html = "".join(
            f'<span class="diq-dx-pill">{_clean_str(dx)}</span>'
            for dx in secondary
            if _clean_str(dx)
        )
        st.markdown(
            '<div style="font-size:0.82rem;color:#64748B;margin-top:14px;">'
            '<b>Also treated during this stay:</b>'
            f'<div style="margin-top:6px;">{pills_html}</div>'
            '</div>',
            unsafe_allow_html=True,
        )


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


def _render_medication_card(med: dict, card_index: int) -> None:
    """
    Render a single medication card with status badge and citation chip.

    Args:
        med:        Medication dict from ExtractionOutput.
        card_index: Zero-based index for unique widget keys.
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

    st.markdown(
        f"""
        <div class="diq-med-card" style="border-left-color:{border_color};">
            <div style="display:flex;align-items:center;justify-content:space-between;">
                <span style="font-weight:700;font-size:0.95rem;color:#1E293B;">
                    {name}
                </span>
                {"<span class='diq-badge' style='background:" + badge_color + ";'>"
                 + badge_label + "</span>" if badge_label else ""}
            </div>
            <div style="font-size:0.82rem;color:#64748B;margin-top:2px;">
                {details}
            </div>
            {changed_banner}
        </div>
        """,
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
        '<div class="diq-section-title">Your Medications</div>',
        unsafe_allow_html=True,
    )

    if not medications:
        st.caption("No medications found in the document.")
        return

    rationale_blocks = _parse_medication_rationale(
        result.get("medication_rationale", "")
    )

    for idx, med in enumerate(medications):
        _render_medication_card(med, idx)

        block = _find_rationale_for_med(med.get("name", ""), rationale_blocks)
        if not block:
            continue

        label = (
            "Why your doctor stopped this"
            if block.get("stopping")
            else "Why you're taking this and what to expect"
        )
        with st.expander(label):
            st.markdown(block.get("text", ""))


# ── Section: Appointments ────────────────────────────────────────────────────

def _render_appointment_row(appt: dict, row_index: int) -> None:
    """
    Render a single follow-up appointment row.

    Every string field is run through _clean_str() before being embedded
    into the unsafe_allow_html markdown block — this is the defensive
    fix for upstream LLM responses that occasionally return HTML-laden
    reason/notes fields.

    Args:
        appt:      FollowUpAppointment dict from ExtractionOutput.
        row_index: Zero-based index for unique widget keys.
    """
    provider = _clean_str(appt.get("provider"))
    specialty = _clean_str(appt.get("specialty"))
    reason = _clean_str(appt.get("reason"))
    # "notes" is not part of the canonical schema but some downstream
    # pipelines do populate it — strip defensively in case it shows up.
    notes = _clean_str(appt.get("notes"))
    date_display = _clean_str(_format_date(appt.get("date")))
    source = appt.get("source")

    display_name = provider or specialty or "Appointment"
    sub_label = specialty if provider and specialty else ""
    details = reason or notes

    sub_html = (
        f"<span style='font-size:0.8rem;color:#64748B;margin-left:6px;'>"
        f"{sub_label}</span>"
        if sub_label else ""
    )
    details_html = (
        f"<div style='font-size:0.82rem;color:#64748B;'>{details}</div>"
        if details else ""
    )

    st.markdown(
        f"""
        <div class="diq-appt-row">
            <div class="diq-appt-dot"></div>
            <div style="flex:1;">
                <div style="font-weight:700;font-size:0.93rem;color:#1E293B;">
                    {display_name}{sub_html}
                </div>
                <div style="font-size:0.85rem;color:#374151;margin-top:2px;">
                    📅 {date_display}
                </div>
                {details_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if source and source.get("page"):
        _citation_button(
            source["page"],
            source.get("text", ""),
            key_suffix=f"appt_{row_index}",
        )


def _render_section_appointments(result: dict) -> None:
    """
    Render the appointments tab.

    Args:
        result: PipelineResponse dict.
    """
    ext = result.get("extraction", {})
    appointments = ext.get("follow_up_appointments", [])

    st.markdown(
        '<div class="diq-section-title">Your Follow-Up Appointments</div>',
        unsafe_allow_html=True,
    )

    if not appointments:
        st.caption("No follow-up appointments found in the document.")
        return

    for idx, appt in enumerate(appointments):
        _render_appointment_row(appt, idx)


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
        '<div class="diq-section-title">Warning Signs</div>',
        unsafe_allow_html=True,
    )

    if not flags and not escalation:
        st.caption("No emergency warning signs listed in the document.")
        return

    if flags:
        flag_rows_html = "".join(
            f'<div class="diq-flag-row">'
            f'<div class="diq-flag-dot"></div>'
            f'<div style="font-size:0.9rem;color:#7F1D1D;">{_clean_str(flag)}</div>'
            f'</div>'
            for flag in flags
        )

        st.markdown(
            '<div class="diq-warning-card">'
            '<div style="font-weight:700;font-size:0.9rem;color:#7F1D1D;margin-bottom:8px;">'
            "Go to the ER or call 911 if you have:"
            "</div>"
            f"{flag_rows_html}"
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
        '<div class="diq-section-title">Recovery Notes</div>',
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

    trajectory = _clean_str(result.get("recovery_trajectory", ""))
    if trajectory:
        st.markdown("---")
        st.markdown("#### Your recovery timeline")
        st.markdown(trajectory)


# ── Section dispatch ─────────────────────────────────────────────────────────

_SECTION_RENDERERS = {
    "diagnosis":    _render_section_diagnosis,
    "medications":  _render_section_medications,
    "appointments": _render_section_appointments,
    "warnings":     _render_section_warning_signs,
    "recovery":     _render_section_recovery,
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
    primary_dx = ext.get("primary_diagnosis", "your condition")
    dx_short = " ".join(primary_dx.split()[:4]).replace("'", "\\'")

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

  // Push Streamlit main content left so it doesn't hide under the panel.
  var mainSection = pdoc.querySelector('section[data-testid="stMain"]');
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
    if (!mainSection) return;
    if (panel && !panel.classList.contains('diq-hidden')) {{
      var w = panel.getBoundingClientRect().width;
      mainSection.style.paddingRight = (w + 16) + 'px';
    }} else {{
      mainSection.style.paddingRight = '';
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

  function appendAiMsg(text, sourcePage) {{
    var wrap = pdoc.createElement('div');
    wrap.className = 'diq-msg-ai';
    wrap.innerHTML = renderMarkdown(text);
    var src = pdoc.createElement('div');
    src.className = 'diq-msg-source';
    src.textContent = sourcePage
      ? '\u2014 from your document (p.' + sourcePage + ')'
      : '\u2014 from your document';
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
    if (msg.role === 'user') appendUserMsg(msg.text);
    else appendAiMsg(msg.text, msg.sourcePage || null);
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
        appendAiMsg('Sorry, I could not reach the assistant. Please try again.', null);
      }} else {{
        var data = await resp.json();
        var reply = data.reply || 'No response received.';
        var sourcePage = data.source_page || null;
        appendAiMsg(reply, sourcePage);
        history.push({{ role: 'ai', text: reply, sourcePage: sourcePage }});
        saveHistory(history);
      }}
    }} catch(err) {{
      var thinkEl2 = pdoc.getElementById('diq-thinking-indicator');
      if (thinkEl2) thinkEl2.remove();
      appendAiMsg('Could not reach the DischargeIQ server. Make sure it is running.', null);
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


# ── Upload screen ─────────────────────────────────────────────────────────────

def _render_upload_screen() -> None:
    """
    Render the initial upload screen — centered hero + file picker.

    Calls _cleanup_parent_dom() first so any header/tab-bar/chat-panel
    left over from a prior session (e.g. after clicking "Upload new")
    is removed from window.parent.document.
    """
    _cleanup_parent_dom()

    _, center_col, _ = st.columns([1, 2, 1])
    with center_col:
        # Hero is ALWAYS rendered first for stable layout order. Once a
        # file is in hand, the hero and uploader are hidden by CSS and
        # only the analyzing card is shown, to avoid the duplicated-hero
        # flash during Streamlit's rerun transition.
        st.markdown(
            """
            <div class="diq-upload-hero"
                 style="text-align:center;padding:52px 0 28px;">
                <h1 style="font-size:2rem;font-weight:800;color:#1E293B;margin:0;">
                    DischargeIQ
                </h1>
                <p style="color:#64748B;font-size:0.97rem;max-width:420px;
                          margin:10px auto 0;line-height:1.6;">
                    Upload your hospital discharge document and get a plain-language
                    summary of your diagnosis, medications, and follow-up care.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        uploaded = st.file_uploader(
            "Choose your discharge PDF",
            type=["pdf"],
            label_visibility="collapsed",
            key="pdf_upload",
        )

        if uploaded is not None:
            # Active state: hide the idle hero + uploader and show one
            # centered analyzing block containing:
            #   - the "Analyzing your discharge document" heading
            #   - a cycling stage label (5 agents) that swaps every ~9s
            #   - a progress bar that smoothly fills 0 → 95% across the
            #     expected pipeline duration; the final jump to 100%
            #     happens when the screen swaps to the summary view.
            # The animation is pure CSS so it keeps painting even while
            # the Python run is blocked on the /analyze call.
            st.markdown(
                """
                <style>
                  .diq-upload-hero { display: none !important; }
                  div[data-testid="stFileUploader"] { display: none !important; }

                  @keyframes diq-progress-fill {
                    0%   { width: 3%; }
                    20%  { width: 28%; }
                    45%  { width: 55%; }
                    70%  { width: 78%; }
                    100% { width: 95%; }
                  }
                  @keyframes diq-bar-shine {
                    0%   { transform: translateX(-100%); }
                    100% { transform: translateX(250%); }
                  }
                  @keyframes diq-stage-cycle {
                    0%, 17%   { opacity: 1; transform: translateY(0); }
                    20%, 97%  { opacity: 0; transform: translateY(6px); }
                    100%      { opacity: 0; }
                  }
                  @keyframes diq-dot-pulse {
                    0%, 80%, 100% { opacity: 0.25; }
                    40%           { opacity: 1; }
                  }

                  .diq-analyzing {
                    display: flex; flex-direction: column;
                    align-items: center; justify-content: center;
                    gap: 18px;
                    padding: 80px 0 40px; text-align: center;
                  }
                  .diq-analyzing h1 {
                    font-size: 1.35rem; font-weight: 700;
                    color: #0f6e56; margin: 0;
                  }
                  .diq-analyzing .diq-sub {
                    color: #64748B; font-size: 0.9rem; margin: 0;
                  }

                  /* Stage label stack — all 5 labels overlap and each
                     fades in/out in sequence for its 9s slot. */
                  .diq-stage {
                    position: relative; height: 22px; width: 320px;
                  }
                  .diq-stage span {
                    position: absolute; inset: 0;
                    display: flex; align-items: center; justify-content: center;
                    color: #0f6e56; font-size: 0.92rem; font-weight: 600;
                    opacity: 0;
                    animation: diq-stage-cycle 45s linear forwards;
                  }
                  .diq-stage span:nth-child(1) { animation-delay: 0s; }
                  .diq-stage span:nth-child(2) { animation-delay: 9s; }
                  .diq-stage span:nth-child(3) { animation-delay: 18s; }
                  .diq-stage span:nth-child(4) { animation-delay: 27s; }
                  .diq-stage span:nth-child(5) { animation-delay: 36s; }

                  /* Progress bar track + fill. */
                  .diq-bar {
                    width: 320px; height: 8px;
                    background: #E2E8F0; border-radius: 999px;
                    overflow: hidden; position: relative;
                  }
                  .diq-bar-fill {
                    height: 100%; width: 3%;
                    background: linear-gradient(90deg, #0f6e56, #10B981);
                    border-radius: 999px; position: relative;
                    animation: diq-progress-fill 45s cubic-bezier(.32,.72,.38,1) forwards;
                  }
                  .diq-bar-fill::after {
                    /* moving shine highlight that sweeps across the fill */
                    content: ""; position: absolute; inset: 0;
                    background: linear-gradient(
                      90deg,
                      transparent 0%,
                      rgba(255,255,255,0.55) 50%,
                      transparent 100%
                    );
                    animation: diq-bar-shine 1.8s linear infinite;
                  }

                  /* Bouncing dots under the progress bar — subtle
                     secondary activity indicator so the UI never looks
                     frozen even after the bar pauses at 95%. */
                  .diq-dots {
                    display: flex; gap: 6px;
                  }
                  .diq-dots span {
                    width: 6px; height: 6px; border-radius: 50%;
                    background: #0f6e56;
                    animation: diq-dot-pulse 1.4s ease-in-out infinite;
                  }
                  .diq-dots span:nth-child(2) { animation-delay: 0.2s; }
                  .diq-dots span:nth-child(3) { animation-delay: 0.4s; }
                </style>
                <div class="diq-analyzing">
                    <h1>Analyzing your discharge document</h1>
                    <div class="diq-stage">
                        <span>Reading your document…</span>
                        <span>Extracting medications &amp; appointments…</span>
                        <span>Explaining your diagnosis in plain language…</span>
                        <span>Mapping your recovery timeline…</span>
                        <span>Checking for warning signs…</span>
                    </div>
                    <div class="diq-bar"><div class="diq-bar-fill"></div></div>
                    <div class="diq-dots"><span></span><span></span><span></span></div>
                    <p class="diq-sub">This usually takes 30–60 seconds.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            pdf_bytes = uploaded.read()
            logger.info("File uploaded: %s (%d bytes)", uploaded.name, len(pdf_bytes))

            try:
                result = _call_analyze(pdf_bytes, uploaded.name)
                st.session_state[_S_RESULT] = result
                st.session_state[_S_PDF_BYTES] = pdf_bytes
                st.session_state[_S_PDF_SESSION_ID] = result.get("pdf_session_id")
                st.session_state[_S_FILE_NAME] = uploaded.name
                st.session_state[_S_ACTIVE_TAB] = "diagnosis"
                st.session_state[_S_PENDING_CITATION] = None
                logger.info(
                    "Pipeline complete — status: %s",
                    result.get("pipeline_status", "unknown"),
                )
                st.rerun()
            except requests.exceptions.ConnectionError:
                st.error(
                    "Could not reach the DischargeIQ backend. "
                    "Start the server with: "
                    "`uvicorn dischargeiq.main:app --reload`"
                )
            except requests.exceptions.Timeout:
                st.error(
                    "The server took too long to respond. "
                    "Please try again or use a smaller PDF."
                )
            except _AnalyzeError as api_err:
                # Map known HTTP codes to a user-friendly message. The raw
                # server detail is logged but never shown — patients should
                # not see stack traces or internal error text.
                logger.error(
                    "Analyze returned %d for '%s': %s",
                    api_err.status, uploaded.name, api_err.message,
                )
                if api_err.status == 413:
                    st.error(
                        "That PDF is too large. The limit is 50MB — "
                        "try compressing it."
                    )
                elif api_err.status == 415:
                    st.error(
                        "That file doesn't look like a PDF. "
                        "Please upload a PDF discharge summary."
                    )
                elif api_err.status == 504:
                    st.error(
                        "Analysis timed out. "
                        "Try a smaller or clearer PDF."
                    )
                elif api_err.status >= 500:
                    st.error(
                        "Something went wrong on our end. Please try again."
                    )
                else:
                    st.error(f"Upload failed ({api_err.status}). Please try again.")
            except Exception as unexpected_err:
                logger.error("Unexpected error during upload: %s", unexpected_err)
                st.error("An unexpected error occurred. Please try again.")


# ── Summary screen ────────────────────────────────────────────────────────────

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

    _render_app_header(result)
    _render_tab_bar(active_tab)

    # Dispatch to the active tab's section renderer — only one section
    # renders per run.
    renderer = _SECTION_RENDERERS.get(active_tab, _render_section_diagnosis)
    renderer(result)

    # One-shot PDF modal. Consume the pending state so the modal does
    # not re-open on the next rerun (e.g. tab switch after user closed it).
    pending = st.session_state[_S_PENDING_CITATION]
    if pending:
        _inject_pdf_modal(pdf_session_id, int(pending.get("page", 1) or 1))
        st.session_state[_S_PENDING_CITATION] = None

    # Chat panel — injected last so it sits above earlier components.
    _render_chat_widget(result)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """
    Main entry point for the Streamlit app.

    Routes between the upload screen (no result in state) and the
    summary screen (result present in state). Called at module level
    because Streamlit executes the file as a script on every rerender.
    """
    # One-shot cleanup: clears window.parent.sessionStorage and any
    # stale injected DOM nodes on fresh page load (survives Cmd-R).
    # No-op on subsequent reruns within the same Streamlit session.
    _clear_browser_session_on_fresh_load()

    _inject_global_css()

    if st.session_state[_S_RESULT] is None:
        _render_upload_screen()
    else:
        _render_summary_screen()


main()
