# Sprint 5 - Clinical Trial and Safety Audit (Weeks 9–10) ◻

| Task | Deliverable | Status |
|---|---|---|
| 5.1 | Clinician onboarding (role-based Streamlit portal, 0–5 rubric) | ✅ built early (Week 2) - [task-5.1](tasks/task-5.1.md) |
| 5.2 | Two clinicians independently score the locked corpus | ◻ - LOF to connect reviewers. **Scored corpus = MTSamples (real documents), rubric fixed July 30 2026.** Anchors are now relative to the source rather than to an ideal summary, because only 34% of real documents contain warning signs and 62% contain discharge medications. Reviewers are told per document: absent from source and absent from output is not a penalty; present in output but not in source is a hallucination. |
| 5.3 | Adversarial safety audit (prompt injection, dosage forcing, zero hallucinations) | ◑ **UNBLOCKED July 30 2026** - `evaluation/adversarial_audit.py` built + runnable (6 cases: 4 injection, 2 corruption); gate logic unit-verified. Billing is restored and the Cloud Run backend runs `llm_provider: vertex`, which is the funded path this task required. Remaining: execute the run and record the result. |
| 5.4 | Fix pass for documents scoring below 4.0 | ◻ - depends on 5.2 scores |

Gate: median ≥ 4.0/5.0, zero medication/diagnostic hallucinations.
