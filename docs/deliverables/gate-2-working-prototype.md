# Gate 2 - Working prototype (end of Week 6, Tue 18 Aug 2026) - $1,250

**Bar:** core capability runs end to end for at least one real path, live or recorded.
> Renamed from the old "tranche" vocabulary on 2026-07-31. docs/LOF_LABS_RULES.md is authoritative and uses 13 weeks, 4 phases, and 3 pass/fail gates plus a final demo; it says explicitly to ignore the word "tranche". The old week numbering (0/4/8/12) came with that vocabulary and did not match the gate dates either.


**Accepted when:** live backend; app installable on real devices; 10–20
active installs; live end-to-end scan-and-translate demo.

> **Re-scoped July 30 2026.** No paid store accounts this summer, so
> "TestFlight and Play" is replaced by: direct-install release APK on
> Android, and free 7-day development provisioning on iOS. The install
> target is met on Android; iOS reach is limited to devices the developer
> provisions in person and reinstalls weekly. Raise with LOF if a shared
> Apple account can be provided (research-before-spend ladder, rung 1).

| Piece | Status | Evidence |
|---|---|---|
| Live cloud backend + 6-agent pipeline | ✅ | Cloud Run URL; sprint-1.md demo |
| Supervisor/router gating | ✅ | `task-1.3-router` tag |
| Model failover + Vertex path + FK gating | ✅ | `task-1.4-failover-vertex` tag; failover fired live during corpus generation |
| Corpus + Neon testing matrix | ✅ | `task-1.5-corpus` tag; `synthetic_corpus` table. Primary corpus moved July 30 2026 to 106 real de-identified MTSamples documents; the 50-doc synthetic set stays version-locked in the tags |
| Camera scan + OCR on device | ◻ Sprint 2 | - |
| Device distribution (APK + 7-day iOS provisioning) + 10–20 installs | ◻ Sprint 2 | Beta kit builds and passes its backend health gate; testers not yet recruited |

Sprint files: [sprint-1.md](sprint-1.md) ✅ · [sprint-2.md](sprint-2.md) ◻
