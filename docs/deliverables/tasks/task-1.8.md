# Task 1.8 - Client-to-Server Integration over TLS ✅

**Deliverable:** the mobile client talks to the backend over TLS, with no
plaintext path available to it.

**Commit:** `e5de64b` (`POST /analyze/text`, the on-device OCR path), hardened
later by `d2f0b93` (bearer key on the LLM-cost routes) and `9df24ce`
(anonymous callers can no longer supply their own grounding context).

**Files:** `dischargeiq_mobile/lib/config.dart` resolves the base URL;
release builds go to Cloud Run over HTTPS and cannot be pointed elsewhere
without a rebuild. `dischargeiq/api/middleware.py` and
`dischargeiq/api/routes/analyze.py` on the server side.

**How TLS is guaranteed rather than assumed:** the release constant is an
`https://` Cloud Run URL, and the debug-only local override is documented in
`config.dart` with an explicit warning never to hardcode a LAN address there,
because a stale entry would send document text over plain HTTP to whoever
holds that IP now. Cloud Run terminates TLS and does not serve the service
over HTTP.

**Demo:**

```bash
python scripts/verify_live_service.py --guardrails    # ~5s, spends nothing
```

Verified 26 Aug 2026: 9 passed, 0 failed. Confirms liveness, that
`/analyze`, `/quiz/*` and `/chat` all return 401 without a key, and that the
API surface stays closed (`/docs`, `/openapi.json`, `/redoc` all 404).
