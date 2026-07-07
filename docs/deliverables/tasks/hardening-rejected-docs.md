# Hardening - First-class Handling of Non-Discharge Documents ✅ (Jul 7 audit)

**Deliverable:** a patient who uploads the wrong PDF (bill, EOB, invoice) gets
one clear screen and a retry - never seven empty tabs, an ungrounded chatbot,
and a quiz generated from nothing.

**Commit / tag:** `5d66d52` / `hardening-rejected-docs`

**Audit finding (severity: high, UX + trust):** the router (Task 1.3)
correctly gated non-discharge documents at the API, but the rejection was
encoded as `pipeline_status="partial"` plus a sentence inside
`extraction_warnings`. Both UIs treated it as a generic degraded run and
rendered the FULL results experience over empty content - including the
"Download summary (PDF)" button and the chat panel with nothing to ground on.
Detection required string-matching warning text (fragile contract).

**Fix (contract-first):**
- `pipeline_status` gains a fourth value: **`"rejected"`**, plus a new
  optional **`rejection_reason`** field carrying the router's one-sentence
  explanation (`dischargeiq/pipeline/orchestrator.py`,
  `dischargeiq/models/pipeline.py`; CLAUDE.md contract updated in both
  places). The old warning string is kept for logs and older clients.
  Rejected documents never reach Agent 1 and never write a DB row.
- **Streamlit:** `_render_rejected_screen` - full-page notice with the
  router's reason, a plain-language description of what a discharge summary
  is, and a single "Try another document" button that resets to upload.
  No tabs, no chat, no quiz, no PDF download.
- **Mobile:** `_RejectedDocumentScreen` in `results_screen.dart` - same
  content, pops back to upload. The first-run guided tour is suppressed on
  rejection (the tab bar it points at does not exist).
- **Test:** `test_router_rejection_returns_rejected_status` asserts the
  status + reason AND that no downstream agent runs on a rejected document
  (any agent call fails the test loudly).

**Verified live:** synthetic plumbing-invoice PDF -> `rejected` with reason
"Document is a plumbing service invoice, not a medical discharge summary";
rejection screen + retry loop driven end-to-end in a real browser;
`heart_failure_01.pdf` still returns `complete` with all four agent texts.
81 backend + 6 Flutter tests green.
