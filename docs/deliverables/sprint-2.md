# Sprint 2 — Mobile Bridge and OCR (Weeks 3–4) ◻ NEXT

**Milestone (Tranche 2 gate):** install the app on a real phone, scan a
discharge document with the camera, get 6th-grade output back — live.

## Tasks

| Task | Deliverable | Status |
|---|---|---|
| 2.1 | Flutter core UI (themes, state, camera + detail screens) | Head start: app already has upload → results → quiz flow |
| 2.2 | Camera + ML Kit OCR pipeline | ✅ `7a2bf9c` — [task-2.2](tasks/task-2.2.md) (edge detection deferred) |
| 2.3 | Client-to-server integration | ✅ — PDF upload + OCR-text path (`e5de64b`) both live |
| 2.4 | TestFlight + Play Internal Testing distribution | ◻ — blocked on developer account verification |
| 2.5 | Beta onboarding (15 testers → 10–20 active installs) | ◻ |

## Risk note

This is the schedule crunch of the summer. Mitigations already in place:
corpus work (1.5/1.6) was pulled into Sprint 1, and the quiz loop (3.1/3.2)
is already built — Sprint 2 is purely camera/OCR/distribution work.
If store review stalls, demo on a direct-install debug build
(`flutter build apk --debug` verified working).
