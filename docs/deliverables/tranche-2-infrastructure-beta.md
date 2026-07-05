# Tranche 2 — Infrastructure and Beta (End of Week 4)

**Accepted when:** live backend; app on TestFlight and Play; 10–20 active
installs; live end-to-end scan-and-translate demo.

| Piece | Status | Evidence |
|---|---|---|
| Live cloud backend + 6-agent pipeline | ✅ | Cloud Run URL; sprint-1.md demo |
| Supervisor/router gating | ✅ | `task-1.3-router` tag |
| Model failover + Vertex path + FK gating | ✅ | `task-1.4-failover-vertex` tag; failover fired live during corpus generation |
| 50-doc corpus + Neon testing matrix | ✅ | `task-1.5-corpus` tag; `synthetic_corpus` table |
| Camera scan + OCR on device | ◻ Sprint 2 | — |
| TestFlight / Play distribution + 10–20 installs | ◻ Sprint 2 | — |

Sprint files: [sprint-1.md](sprint-1.md) ✅ · [sprint-2.md](sprint-2.md) ◻
