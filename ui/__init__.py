"""
ui/ - Streamlit UI modules extracted from streamlit_app.py.

streamlit_app.py is the entry point and tab host; per-tab section renderers
migrate here one module at a time (first: quiz_tab). New tabs go here
directly - never grow the monolith.

Also holds helpers shared by the entry point and the tab modules, so neither
has to import the other (streamlit_app imports ui, never the reverse).
"""

import os


def api_auth_headers() -> dict[str, str]:
    """
    Authorization header for backend calls, or empty when no key is set.

    The backend skips its API-key check entirely when DISCHARGEIQ_API_KEY is
    unset (local dev), so sending no header is correct there. Any deployment
    that sets the key rejects unauthenticated calls with 401, so every
    server-side request must spread this into its headers.

    Returns:
        dict[str, str]: {"Authorization": "Bearer <key>"} or {} when unset.
    """
    key = os.environ.get("DISCHARGEIQ_API_KEY", "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}
