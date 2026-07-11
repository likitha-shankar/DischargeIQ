# Sprint 5 - Clinical Trial and Safety Audit (Weeks 9–10) ◻

| Task | Deliverable | Status |
|---|---|---|
| 5.1 | Clinician onboarding (role-based Streamlit portal, 0–5 rubric) | ✅ built early (Week 2) - [task-5.1](tasks/task-5.1.md) |
| 5.2 | Two clinicians independently score the locked 50-doc corpus | ◻ - LOF to connect reviewers |
| 5.3 | Adversarial safety audit (prompt injection, dosage forcing, zero hallucinations) | ◑ - `evaluation/adversarial_audit.py` built + runnable (6 cases: 4 injection, 2 corruption); gate logic unit-verified. Needs a valid live run under real quota / Vertex (last run degraded on exhausted free-tier) |
| 5.4 | Fix pass for documents scoring below 4.0 | ◻ - depends on 5.2 scores |

Gate: median ≥ 4.0/5.0, zero medication/diagnostic hallucinations.
