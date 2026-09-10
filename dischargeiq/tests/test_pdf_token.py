"""
Signed access to a patient's stored PDF.

Before this, GET /pdf/{session_id} returned the document to anyone holding the
URL. Verified against production on 9 Sep 2026: no auth header, HTTP 200,
200586 bytes of a real PDF. A UUID4 is unguessable, but it never expired,
could not be revoked, and was written to the application logs where anyone
with log access could replay it.

A Bearer header is not available here: the Streamlit viewer renders the
document in an <iframe>, and a browser iframe cannot attach one. So the
credential travels in the URL, which is weaker by nature - URLs reach browser
history, referrer headers and proxy logs - and therefore has to expire.

Every test below is a property an attacker would try to break.
"""

import os
import time

import pytest

from dischargeiq.utils import pdf_token as pt


@pytest.fixture(autouse=True)
def _with_api_key(monkeypatch):
    """Gating is on only when an API key is configured; assume it is."""
    monkeypatch.setenv("DISCHARGEIQ_API_KEY", "test-key-for-signing")


class TestAValidTokenWorks:
    def test_a_freshly_minted_token_verifies(self):
        token, exp = pt.mint_pdf_token("session-a")
        assert pt.verify_pdf_token("session-a", token, exp)

    def test_the_expiry_is_in_the_future(self):
        _, exp = pt.mint_pdf_token("session-a")
        assert exp > time.time()

    def test_it_still_works_shortly_before_expiry(self):
        token, exp = pt.mint_pdf_token("session-a")
        assert pt.verify_pdf_token("session-a", token, exp, now=exp - 1)


class TestWhatMustBeRejected:
    """Each of these returned a patient's document before today."""

    def test_no_token_at_all(self):
        assert not pt.verify_pdf_token("session-a", None, None)

    def test_a_token_with_no_expiry(self):
        token, _ = pt.mint_pdf_token("session-a")
        assert not pt.verify_pdf_token("session-a", token, None)

    def test_an_expired_token(self):
        token, exp = pt.mint_pdf_token("session-a")
        assert not pt.verify_pdf_token("session-a", token, exp, now=exp + 1)

    def test_a_tampered_signature(self):
        token, exp = pt.mint_pdf_token("session-a")
        assert not pt.verify_pdf_token("session-a", token[:-1] + "0", exp)

    def test_extending_the_expiry_invalidates_the_token(self):
        """
        The expiry is inside the signed payload for this reason. If only the
        session were signed, a caller could keep a token alive forever by
        editing `exp` in the URL, and the expiry would be decorative.
        """
        token, exp = pt.mint_pdf_token("session-a")
        assert not pt.verify_pdf_token("session-a", token, exp + 86400)

    def test_a_token_for_another_session_does_not_open_this_one(self):
        """
        Otherwise one patient's valid token would fetch every document held
        by the process.
        """
        token, exp = pt.mint_pdf_token("session-a")
        assert not pt.verify_pdf_token("session-b", token, exp)

    @pytest.mark.parametrize("exp", ["not-a-number", "", "1e9999", None])
    def test_a_malformed_expiry_is_rejected_not_crashed_on(self, exp):
        token, _ = pt.mint_pdf_token("session-a")
        assert not pt.verify_pdf_token("session-a", token, exp)

    def test_a_token_signed_with_a_different_secret_fails(self, monkeypatch):
        """Rotating the API key must invalidate tokens minted under the old one."""
        token, exp = pt.mint_pdf_token("session-a")
        monkeypatch.setenv("DISCHARGEIQ_API_KEY", "a-different-key")
        assert not pt.verify_pdf_token("session-a", token, exp)


class TestLocalDevelopmentIsUnaffected:
    """
    verify_api_key skips entirely when no API key is set - that is deliberate
    open dev mode. One endpoint quietly starting to reject requests in that
    mode would be a surprise, not a safeguard.
    """

    def test_gating_is_off_without_an_api_key(self, monkeypatch):
        monkeypatch.delenv("DISCHARGEIQ_API_KEY", raising=False)
        assert not pt.tokens_required()
        assert pt.verify_pdf_token("session-a", None, None)

    def test_gating_is_on_with_one(self):
        assert pt.tokens_required()
        assert not pt.verify_pdf_token("session-a", None, None)

    def test_a_whitespace_only_key_counts_as_unset(self, monkeypatch):
        monkeypatch.setenv("DISCHARGEIQ_API_KEY", "   ")
        assert not pt.tokens_required()


class TestTheSignatureItself:
    def test_two_sessions_get_different_signatures(self):
        a, exp = pt.mint_pdf_token("session-a")
        b, _ = pt.mint_pdf_token("session-b", now=exp - pt._TOKEN_TTL_SECONDS)
        assert a != b

    def test_the_token_leaks_nothing_about_the_key(self):
        token, _ = pt.mint_pdf_token("session-a")
        assert os.environ["DISCHARGEIQ_API_KEY"] not in token
        assert len(token) == 64  # hex sha256, no truncation
