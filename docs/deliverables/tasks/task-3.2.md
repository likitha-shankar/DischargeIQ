# Task 3.2 - Gamified Quiz UI (mobile + web fallback) ✅ (built early, Week 2)

**Deliverable:** the full gamified loop on both surfaces. The phone app is the
primary product; Streamlit mirrors it as the fallback/demo surface.

**Commits / tags:** `a7359fc` / `task-3.2-quiz-mobile`, `de6d126` / `task-3.2-quiz-web`

**Flow (identical on both):** intro → baseline quiz (NO correctness feedback -
the baseline must not teach) → learning cards per domain, built from the
patient's own pipeline output → post-quiz (same frozen questions, shuffled
order, instant feedback + plain-language explanations) → results (animated
score ring, before/after lift banner, per-domain chips) → mastery path: any
failed domain forces a focused review of just those cards before retaking.

**Files:** `dischargeiq_mobile/lib/{models/quiz.dart, screens/quiz_screen.dart,
widgets/quiz_widgets.dart}` + "Test yourself" tab in results;
`ui/quiz_tab.py` + tab wiring in `streamlit_app.py`.

**Resilience:** if the API is unreachable mid-quiz, scoring falls back to a
local computation - the flow never dead-ends. `flutter analyze` clean; debug
APK builds; Streamlit boots clean.

---

## Game layer v2 (Jul 5) - `477d10e` / `task-3.2-game-v2`

Accuracy streak chip, haptics, praise lines, confetti gated to
improved/perfect scores (research-informed: rare celebrations register as
meaningful; no timers or speed points, which pressure older or unwell
patients).

## Game layer v3 (Jul 7) - pending review, suggested tag `task-3.2-game-v3`

Both surfaces, same rules:
- **"Master it" round:** after a mastery review, the post retake re-asks ONLY
  the missed questions - correct answers carry over, the retake is short and
  winnable. Scoring still submits the full answer set as phase `post`, so the
  server contract and the stored comprehension delta are unchanged.
- **XP + levels:** 10 XP per correct answer, 25 per finished round, 50 bonus
  on first full mastery; 8 level thresholds (100 -> 1900 XP). Anti-farming:
  XP counts only questions asked in the round; the mastery bonus fires once
  per transition into mastery.
- **Mastery badges:** per-domain three-step ladder (Keep learning / Almost
  there / Mastered); a badge once earned never downgrades.
- **Personal bests + welcome-back:** best score, biggest lift, quizzes done,
  level. Mobile persists on-device via SharedPreferences
  (`lib/services/game_store.dart` - engagement state only, never clinical
  data); Streamlit is session-scoped (fallback surface has no device store).

Files: `lib/services/game_store.dart` + `lib/widgets/game_widgets.dart` (new),
`lib/screens/quiz_screen.dart` + `ui/quiz_tab.py` (wired), `DomainChips`
deleted from `quiz_widgets.dart`. Tests: `test/game_store_test.dart` (5 green).
