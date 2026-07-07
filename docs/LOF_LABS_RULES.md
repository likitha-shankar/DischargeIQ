# LOF LABS Program Rules (binding) - DischargeIQ

Source: LOF AI Build Studio (LABS) Participant Guide, Summer 2026.
This file is the authoritative record of program rules for AI agents and the
developer. A compact summary is mirrored into `CLAUDE.md` so it loads every
session. **When the guide and older `CLAUDE.md` text disagree, this file wins.**

Last synced from the guide: 2026-07-07.

## Program shape

- **13 weeks, 4 phases, 3 pass/fail gates**, then a final demo. (NOT "tranches"
  - older docs used that word; ignore it.)
- Evaluated against a **fixed quality bar per gate**, not against other teams.
  No finalist cap: clear the gate and you continue.
- **This is a SOLO project** - Likitha Shankar is the sole developer. There
  are no teammates. Do not add other names anywhere.

## Gates, timing, and awards (up to $5,000)

| Gate / milestone | Timing | Bar | Award | Cumulative |
|---|---|---|---|---|
| Gate 1: Concept approved | End of Week 2 | Clear problem, users, scope, roles, repo+LICENSE ready | $500 | $500 |
| Gate 2: Working prototype | End of Week 6 | Core capability runs end to end for ≥1 real path, live/recorded | $1,250 | $1,750 |
| Gate 3: Feature-complete beta | End of Week 10 | All approved scope present, stable, demo-able without major gaps | $1,250 | $3,000 |
| Final demo | Week 13 | Completed project presented | $2,000 | $5,000 |

- **Cure window:** miss a gate → written feedback + **one week** to fix ONLY
  the flagged criteria. Fix the exact gaps, do not redesign. Passing during
  the cure window still earns the award. Failing after it = exit the program.
- Next-phase work may proceed in parallel during a cure window, at own risk.

## Gate 3 checklist (the main quality filter - Week 10)

- [ ] Every feature in the **approved scope** is present and functional.
- [ ] Runs the full intended demo flow without crashing or blocking bugs.
- [ ] Behaves reasonably on bad input / failure, not just the happy path.
- [ ] Someone who did not build it can complete the main task with minimal help.
- [ ] Nothing core is missing.
- [ ] Repository, LICENSE, and dependency/license manifest are current.

## Repository, license, and data rules (checked at EVERY gate)

1. **Authoritative repo must be LOF-controlled** (LOF GitHub/Bitbucket org).
   A personal GitHub is NOT the authoritative project repo. → **ACTION
   PENDING:** currently on `github.com/likitha-shankar/DischargeIQ`; move to
   the LOF org repo when access is granted, then push there.
2. **LICENSE file at repo root, default Apache License 2.0.** → DONE
   (`LICENSE`, Copyright 2026 Likitha Shankar).
3. **Dependency/license manifest kept current.** → DONE (`DEPENDENCIES.md`);
   regenerate when dependencies change.
4. **No GPL/AGPL or network-copyleft** components without written LOF+IIT
   approval. → Current tree has no AGPL/GPL-only; two weak-copyleft items
   (`fpdf2` LGPL, `pyphen` tri-license) are documented in `DEPENDENCIES.md`.
5. **No program-provided, clinical, patient-derived, OR synthetic/sample/
   evaluation data in PUBLIC repos** without written approval. → The 50
   synthetic PDFs in `test-data/synthetic/` are fine only if the repo is
   private; confirm before pushing anywhere public.

## Healthcare & AI expectations

- State the intended user and the real workflow the tool fits.
- Be explicit about what the AI does and does NOT do. No unsupported clinical
  claims - assist / summarize / organize / educate / triage only within a
  defensible scope. (Matches DischargeIQ's HITL framing and hard rules.)
- Show behavior on incomplete, confusing, out-of-scope, or wrong input.
- Use realistic data carefully; follow all data restrictions.

## Evidence & demo discipline

- Every gate: a runnable build, a short demo script, a README with setup +
  current limitations, screenshots or a backup recording, and a current
  dependency/license manifest.
- Commit source and docs throughout the week, not only before reviews.
- Demo: narrow, rehearsed, honest about limitations; show the core flow
  completely rather than ten partial features; make clear what changed since
  the last gate; have a backup recording ready.

## Standing action items (keep current)

- [ ] Move authoritative repo to the LOF-controlled org (waiting on access).
- [ ] Confirm repo privacy before any push (synthetic data rule).
- [x] Apache-2.0 LICENSE at root.
- [x] `DEPENDENCIES.md` manifest.
- [x] Solo-project: all prior collaborator names removed.
