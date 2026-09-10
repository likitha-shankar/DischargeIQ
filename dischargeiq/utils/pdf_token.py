"""
File: dischargeiq/utils/pdf_token.py
Owner: Likitha Shankar
Description: Short-lived signed tokens for GET /pdf/{session_id}, so a patient's
  document is protected by something that expires rather than by a URL that does not.
Key functions/classes: mint_pdf_token, verify_pdf_token, tokens_required
Edge cases handled:
  - No DISCHARGEIQ_API_KEY means auth is off entirely, and so is this, matching
    verify_api_key; expired and tampered tokens are rejected identically.
Dependencies: stdlib only (hmac, hashlib, time, os).
Called by: dischargeiq.api.routes.pdf (verify), dischargeiq.api.routes.analyze (mint).

WHY A QUERY-STRING TOKEN AND NOT A BEARER HEADER
------------------------------------------------
The obvious protection for GET /pdf/{session_id} is Depends(verify_api_key),
and it does not work here. The Streamlit viewer renders the document with

    <iframe src="{API}/pdf/{session_id}#page=3">

and a browser iframe cannot attach an Authorization header. Gating the route
would leave the viewer showing a 401 instead of the patient's document.

So the credential has to travel in the URL. That is weaker than a header by
nature - URLs land in browser history, referrer headers and proxy logs - which
is exactly why this one EXPIRES. A leaked link stops working; a leaked session
id used to work forever.

WHAT THIS REPLACES
------------------
Before: the session id alone fetched the document. Verified against production
on 9 Sep 2026 - no auth header, HTTP 200, 200586 bytes of a real PDF. A UUID4
is unguessable, but it never expired, could not be revoked, and was written to
the application logs, where anyone with log access could replay it.

WHAT IT STILL DOES NOT DO
-------------------------
No revocation before expiry, and no per-user binding - anyone holding a valid
token within its window can fetch that one document. Fixing those means real
sessions and user accounts, which this product does not have. The window is
the control, so keep it short.
"""

import hashlib
import hmac
import os
import time

#: How long a minted token stays valid. Long enough to read a discharge
#: summary in one sitting, short enough that a link pasted somewhere it should
#: not be goes dead the same afternoon.
_TOKEN_TTL_SECONDS = int(os.environ.get("PDF_TOKEN_TTL_SECONDS", 30 * 60))

#: Per-process fallback secret, used only when no API key is configured -
#: local development, where auth is off anyway. Regenerated on restart, which
#: is correct: tokens should not outlive the process that has the documents.
_DEV_SECRET = os.urandom(32).hex()


def tokens_required() -> bool:
    """
    Whether PDF access should be gated at all.

    Returns:
        bool: True when DISCHARGEIQ_API_KEY is set.

    Note:
        Mirrors verify_api_key exactly. A deployment with no API key has auth
        switched off deliberately (local dev), and having ONE endpoint start
        rejecting requests in that mode would be a surprise, not a safeguard.
    """
    return bool(os.environ.get("DISCHARGEIQ_API_KEY", "").strip())


def _secret() -> str:
    """Signing secret: the API key where there is one, else a dev value."""
    return os.environ.get("DISCHARGEIQ_API_KEY", "").strip() or _DEV_SECRET


def _sign(session_id: str, expires_at: int) -> str:
    """
    HMAC-SHA256 over the session and its expiry.

    The expiry is INSIDE the signed payload. Signing the session alone would
    let a caller keep a token forever by editing the `exp` parameter, which
    would make the expiry decorative.
    """
    payload = f"{session_id}:{expires_at}".encode()
    return hmac.new(_secret().encode(), payload, hashlib.sha256).hexdigest()


def mint_pdf_token(session_id: str, now: float | None = None) -> tuple[str, int]:
    """
    Create a token authorising one session's PDF for a limited time.

    Args:
        session_id: The session whose document this authorises.
        now: Reference timestamp, for tests. Uses time.time() when None.

    Returns:
        tuple[str, int]: (token, unix expiry). Both belong in the URL - the
        server needs the expiry to recompute the signature.
    """
    expires_at = int((time.time() if now is None else now) + _TOKEN_TTL_SECONDS)
    return _sign(session_id, expires_at), expires_at


def verify_pdf_token(
    session_id: str,
    token: str | None,
    expires_at: str | int | None,
    now: float | None = None,
) -> bool:
    """
    Check a token authorises this session and has not expired.

    Args:
        session_id: Session from the request path.
        token: `token` query parameter.
        expires_at: `exp` query parameter.
        now: Reference timestamp, for tests.

    Returns:
        bool: True when the request may proceed.

    Note:
        Compared with hmac.compare_digest, so a caller cannot narrow the
        signature by timing repeated guesses.

        A token for a DIFFERENT session fails here even when it is otherwise
        valid and unexpired, because the session is inside the signed payload.
        Without that, one document's token would open every document.
    """
    if not tokens_required():
        return True
    if not token or expires_at is None:
        return False
    try:
        expiry = int(expires_at)
    except (TypeError, ValueError):
        return False
    if (time.time() if now is None else now) > expiry:
        return False
    return hmac.compare_digest(_sign(session_id, expiry), token)
