# Task 4.8 - Demo Package ◑

**Deliverable:** rehearsed script, stable dataset, backup recording.

## Done

**Live script:** `docs/DEMO_SCRIPT.md` - follows the LOF Participant Guide
section 9 (problem, user, workflow, core feature, evidence, limitations, next
steps). Narrow, rehearsed, honest about limits.

**External video script:** `docs/DEMO_VIDEO_SCRIPT.md` (`321fbad`), LOF
action item 37:44.

**Offline fallback:** `docs/demo_fallback.html` plus
`scripts/build_demo_fallback.py`. Renders a real captured pipeline result as
a static page, so a demo survives a dead network or a 429 storm. Built
because Vertex runs on dynamic shared quota - the 429s cannot be paced away
and cannot be pre-empted by requesting more.

**Stable dataset:** three sample PDFs at the top of `test-data/`, tracked on
purpose - the beta kit ships them and `scripts/verify_live_service.py` drives
them.

**Recording runbook:** `f861677`.

## Not done

**The recording itself**, and a full rehearsal of the six-step live demo
across phone and dashboard.

## Failure paths worth showing, because Gate 3 asks for them

Four exist and are demonstrable:

1. **Rejected document** - upload the plumbing invoice; the router gates it
   before any agent spends a token and names the reason.
2. **Missing media** - the audio card hides itself rather than showing a
   dead control.
3. **Degraded database** - `/api/health` reports `degraded` with a reason
   instead of failing silently.
4. **Degraded source** (new, 8 Sep) - a scanned document raises the notice
   telling the patient their specific warning signs may be incomplete.

The fourth is the strongest to show a clinical reviewer: it is the system
disclosing its own limitation to the patient, which is the whole HITL framing
in one screen.
