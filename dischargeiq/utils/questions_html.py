"""
File: dischargeiq/utils/questions_html.py
Owner: Likitha Shankar
Description: Pure HTML-builder for the 'Questions to bring to your care team'
  section rendered in the AI Review tab.  Kept separate from streamlit_app.py so
  it can be unit-tested without importing the Streamlit runtime.
Key functions/classes: build_questions_section_html, build_copy_button_html
Edge cases handled:
  - Empty gaps list → returns empty string (caller skips rendering).
  - Questions are HTML-escaped so user-visible text cannot inject markup.
Dependencies: html (stdlib only)
Called by: streamlit_app._render_section_simulator
"""

import html as _html
import json as _json


def build_questions_section_html(gaps: list) -> str:
    """
    Build the static HTML for the numbered questions list section.

    Only call when at least one concept has answered_by_doc=False.
    If gaps is empty the function returns an empty string and the caller
    should skip rendering entirely.

    Args:
        gaps: List of concept dicts where answered_by_doc is False.
              Each dict is expected to have a 'question' key (str).

    Returns:
        str: HTML string for the section heading, patient instruction line,
             and numbered question list.  Empty string when gaps is empty.
    """
    if not gaps:
        return ""

    items = "".join(
        f'<div style="font-size:0.88rem;color:#1E293B;padding:6px 0 6px 4px;'
        f'border-bottom:1px solid #F1F5F9;">'
        f'<span style="color:#64748B;margin-right:8px;font-weight:700;">{i + 1}.</span>'
        f'{_html.escape(str(concept.get("question", "")))}'
        f'</div>'
        for i, concept in enumerate(gaps)
    )

    return (
        '<div class="diq-section-title" style="margin-top:24px;">'
        'Questions to bring to your care team</div>'
        '<p style="font-size:0.83rem;color:#475569;margin:0 0 10px;">'
        'Screenshot this list or read it to your nurse before you leave.</p>'
        f'<div style="margin-bottom:12px;">{items}</div>'
    )


def build_copy_button_html(gaps: list) -> str:
    """
    Build a self-contained HTML document containing the 'Copy questions' button.

    Renders inside a st.components.v1.html iframe.  The button calls
    window.parent.navigator.clipboard.writeText() so the text lands in the
    clipboard of the host browser window (not the sandboxed iframe).

    Args:
        gaps: Same unanswered-concept list passed to build_questions_section_html.

    Returns:
        str: Full HTML document string for st.components.v1.html().
             Empty string when gaps is empty.
    """
    if not gaps:
        return ""

    lines = [
        f"{i + 1}. {str(concept.get('question', ''))}"
        for i, concept in enumerate(gaps)
    ]
    questions_json = _json.dumps("\n".join(lines))

    return f"""<!DOCTYPE html>
<html><head><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:transparent;padding:4px 0}}
#diq-copy-btn{{
  background:#F8FAFC;border:1px solid #CBD5E1;border-radius:6px;
  padding:7px 18px;font-size:0.82rem;font-weight:600;color:#475569;
  cursor:pointer;font-family:inherit;transition:background 0.15s;
}}
#diq-copy-btn:hover{{background:#E2E8F0}}
#diq-copy-btn.copied{{background:#D1FAE5;border-color:#6EE7B7;color:#065F46}}
</style></head>
<body>
<button id="diq-copy-btn">Copy questions</button>
<script>
(function(){{
  var btn = document.getElementById('diq-copy-btn');
  var text = {questions_json};
  function onSuccess(){{
    btn.textContent = 'Copied';
    btn.classList.add('copied');
    setTimeout(function(){{
      btn.textContent = 'Copy questions';
      btn.classList.remove('copied');
    }}, 2000);
  }}
  function fallback(){{
    var ta = window.parent.document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    window.parent.document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {{ window.parent.document.execCommand('copy'); }} catch(e) {{}}
    window.parent.document.body.removeChild(ta);
    onSuccess();
  }}
  btn.addEventListener('click', function(){{
    try {{
      window.parent.navigator.clipboard.writeText(text).then(onSuccess, fallback);
    }} catch(e) {{
      fallback();
    }}
  }});
}})();
</script>
</body></html>"""
