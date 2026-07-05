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
