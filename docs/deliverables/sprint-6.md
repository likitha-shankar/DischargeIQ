# Sprint 6 - Final Polish and Packaging (Weeks 11–12) ◻

| Task | Deliverable | Status |
|---|---|---|
| 6.1 | UI/UX polish, accessibility, graceful degradation | ◑ - rejected-doc screens + media text-fallback shipped; final polish pass ◻ |
| 6.2 | Production builds (locked deps, release iOS/Android) | ◑ - Python deps locked (`requirements.lock.txt`). **Re-scoped July 30 2026:** store-signed production builds are out of scope with no paid accounts. "Production build" for this project means the release APK in the beta kit and a release iOS build installed via 7-day development provisioning. |
| 6.3 | Integration-readiness docs + Vertex AI/BAA deployment runbook | ✅ - `docs/INTEGRATION_READINESS.md` (endpoints, output schema, EHR seam `/analyze/text`, Vertex/BAA runbook). Vertex code path shipped `b2e07b2` |
| 6.4 | Tranche 4 summary report (clinical scores, lift, telemetry) | ◻ - aggregates 5.2 scores when available |
| 6.5 | Fallback verification: 3 forced media-failure modes, no crash | ✅ - `dischargeiq/tests/test_media_fallback.py` (missing / malformed / selector-break; comprehension loop asserted alive each mode). 7 green with existing media tests |
