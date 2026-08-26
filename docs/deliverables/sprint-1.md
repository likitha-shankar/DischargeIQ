# Sprint 1 - Mobile Core on a Real Phone (Weeks 1-2, closed Tue 21 Jul 2026) ✅

Task IDs and wording follow `docs/DischargeIQ_WorkPlan_v2.pdf` (13 Jul 2026),
which is the accepted plan. Checkpoint weeks count from the 8 Jul build start.

**Checkpoint 1 accepted when:** the Sprint 1 demo runs live on a phone, all
nine steps; the beta kit and the version-locked 50-document corpus are
delivered.

| Task | Deliverable | Status | Detail |
|---|---|---|---|
| 1.1 | Cloud infrastructure, pooled DB, PHI-free schema | ✅ | [task-1.1](tasks/task-1.1.md) |
| 1.2 | Containerised FastAPI on Cloud Run | ✅ | [task-1.2](tasks/task-1.2.md) |
| 1.3 | Multi-agent pipeline with router gate | ✅ `220c118` | [task-1.3](tasks/task-1.3.md) |
| 1.4 | Model routing: Gemini primary, Claude failover, Vertex/BAA path, FK gate | ✅ `26a761a`, `b2e07b2` | [task-1.4](tasks/task-1.4.md) |
| 1.5 | 50-document synthetic corpus, SHA-256 version lock | ✅ `42d0f43`, `ddad5bb` | [task-1.5](tasks/task-1.5.md) |
| 1.6 | Corpus loaded to the database as a 5x10 testing matrix | ✅ `b8d2cdf` | [task-1.6](tasks/task-1.6.md) |
| 1.7 | Camera capture and on-device ML Kit OCR | ✅ `7a2bf9c` | [task-2.2](tasks/task-2.2.md) |
| 1.8 | Client-to-server integration over TLS | ✅ `e5de64b` | [task-1.8](tasks/task-1.8.md) |
| 1.9 | Grounded chatbot on mobile | ✅ `9df24ce` | [task-1.9](tasks/task-1.9.md) |
| 1.10 | Android beta kit: APK, guide, samples, manifest | ✅ `61ac8af` | [task-1.10](tasks/task-1.10-android-apk.md) |

## Corpus note (31 Jul 2026)

The version-locked 50-document synthetic corpus delivered at this checkpoint
still exists and still verifies: `git checkout task-4.4-corpus-lock --
test-data/synthetic` restores it, and `scripts/lock_corpus.py --verify`
reproduces the original combined hash `4f0b4250...`. Since then the primary
testing corpus has moved to 106 real de-identified MTSamples documents; see
the index for why.

**Checkout point:** `git checkout sprint-1-complete`
