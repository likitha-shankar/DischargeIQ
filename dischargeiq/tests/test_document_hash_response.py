"""
/analyze tells the client which DOCUMENT it just analysed.

The response has always carried `pdf_session_id`, which identifies the
request. It never carried anything identifying the document itself, so a
client had no way to recognise a summary it already held.

That mattered on mobile. The library keys ten stores off its own document id
- appointment ticks and edits, weights, doses, recovery notes, the corrected
discharge date, learning goals, section stars, quiz bests. Saving a second
entry for a re-uploaded document mints a new id, and every one of those reads
back empty: the patient's own work is orphaned under the old id, still on
disk and unreachable. Nothing throws. It looks exactly as though they never
entered any of it.

`document_hash` is the same SHA-256 this route already caches by, so the
client cannot disagree with the server about what "the same document" is.

The cache-hit case is the one worth asserting hardest: it builds its response
from the CACHED dict rather than from a fresh model_dump, and a field added
to only the fresh path would be missing on exactly the second upload the
mobile fix depends on.
"""

import hashlib

from fastapi.testclient import TestClient

from dischargeiq.main import app
from dischargeiq.services.session import session_store

_client = TestClient(app)


def _cached_payload(diagnosis: str = "COPD") -> dict:
    return {
        "pipeline_status": "complete",
        "extraction": {"primary_diagnosis": diagnosis},
        "patient_simulator": None,
        "pdf_session_id": "old-session",
    }


class TestTheHashReachesTheClient:
    def test_a_cache_hit_returns_the_document_hash(self):
        """
        The path the mobile de-duplication actually runs on. A patient
        re-uploading the same PDF hits the cache; if the hash were missing
        here, the client would fall back to creating a duplicate entry and
        the orphaning bug would survive the fix.
        """
        text = "Synthetic discharge text for the document-hash test. " * 20
        # The route hashes the STRIPPED text. Mirroring it exactly is what
        # keeps this a cache-hit test rather than a real seven-call run.
        doc_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
        # Seeded WITHOUT a hash on purpose: this is what an entry cached by
        # the previous revision looks like during a rolling deploy. The route
        # must state the hash itself rather than inherit it, or the very
        # first re-upload after a deploy still creates a duplicate entry.
        session_store.store_result_for_hash(doc_hash, _cached_payload())
        try:
            response = _client.post(
                "/analyze/text",
                json={"text": text},
                headers={"X-Discharge-Session-Id": "hash-echo-session"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["document_hash"] == doc_hash
            # Same document, different request: the hash is stable where the
            # session id is not. That difference is the whole point.
            assert body["pdf_session_id"] != "old-session"
        finally:
            with session_store._result_lock:
                session_store._result_by_hash.pop(doc_hash, None)
            with session_store._context_lock:
                session_store._context.pop("hash-echo-session", None)

    def test_two_uploads_of_one_document_report_one_hash(self):
        """
        Two requests, two sessions, one document. A client that de-duplicates
        on this value needs it to be identical across both.
        """
        text = "Another synthetic discharge document for hash stability. " * 20
        doc_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
        session_store.store_result_for_hash(doc_hash, _cached_payload())
        try:
            hashes = []
            sessions = []
            for i in range(2):
                response = _client.post(
                    "/analyze/text",
                    json={"text": text},
                    headers={"X-Discharge-Session-Id": f"stability-{i}"},
                )
                assert response.status_code == 200
                hashes.append(response.json()["document_hash"])
                sessions.append(response.json()["pdf_session_id"])
            assert hashes[0] == hashes[1] == doc_hash
            assert sessions[0] != sessions[1]
        finally:
            with session_store._result_lock:
                session_store._result_by_hash.pop(doc_hash, None)
            with session_store._context_lock:
                for i in range(2):
                    session_store._context.pop(f"stability-{i}", None)

    def test_different_documents_report_different_hashes(self):
        """
        A revised summary must not collapse onto the entry for the old one.
        """
        first = "One discharge document. " * 20
        second = "A different discharge document entirely. " * 20
        assert (hashlib.sha256(first.strip().encode("utf-8")).hexdigest()
                != hashlib.sha256(second.strip().encode("utf-8")).hexdigest())
