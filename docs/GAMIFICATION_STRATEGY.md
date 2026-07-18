# DischargeIQ - Gamification Strategy

**Author:** Likitha Shankar
**Date:** July 11, 2026
**For:** Leap of Faith, LLC (John Trzesniak, Tanuj Pravin)
**Fulfills:** Work Plan v2, task 2.3 (gamification strategy document)

## 1. What "gamification" means here (and what it does not)

Per the July review meeting: gamification is **game-like rewards layered on a
process** to keep people engaged, not flashcards, not quizzes, and not a
separate game. In DischargeIQ the process is *understanding your discharge
instructions*. The teach-back quiz is the comprehension instrument; the
rewards are the engagement layer on top of it.

The honest claim, stated plainly (John's eMed reward-system experience):
**rewards can increase interest and engagement; they are not claimed to
guarantee adherence.** We measure engagement and comprehension lift, not a
clinical adherence outcome.

## 2. What the evidence says

A scoping review of gamification and incentives in medication-adherence apps
found that most studies reported improved or sustained adherence, but with
high heterogeneity and weak methodology; points, streaks, and virtual rewards
were the common mechanics, and patients flagged **repetitiveness and
irrelevant features** as the main turn-offs (JMIR mHealth 2022). A depression
meta-analysis found gamification did **not** significantly move the clinical
outcome, a caution against overclaiming (JMIR 2021). Physical-activity trials
show the clearest positive engagement effect.

The design lesson across all of it, framed by Self-Determination Theory
(autonomy, competence, relatedness): gamification helps when it **supports
competence and autonomy**, and backfires when continuous rewards and pressure
**drain the user** ("from immersion to burnout", PMC 2025). For older or
unwell patients specifically, designs must let the user **set their own pace**
and avoid anxiety-inducing mechanics.

**Design rules we adopt from this:**
1. Reward comprehension and completion, never speed. No timers, no countdowns.
2. Rare, meaningful celebration beats constant confetti (avoids reward fatigue).
3. Every reward maps to a real health-literacy step, so it is never irrelevant.
4. The app is fully usable with rewards ignored (autonomy; rewards are opt-in feel, not a gate).
5. No streak punishment or loss language (no burnout, no guilt for a missed day).

## 3. The reward mechanics

### 3.1 Points (XP) - progress signal
- 10 XP per correct teach-back answer.
- 25 XP per finished quiz round.
- 50 XP bonus the first time a patient masters every domain.
- Anti-farming: XP counts only questions actually asked in a round; the mastery
  bonus fires once per transition into mastery, not per replay.

### 3.2 Stars - discharge-process step completion (the engagement layer)
A star for each concrete step of working through the discharge instructions:
- Read each section of the plain-language breakdown (diagnosis, medications,
  appointments, warning signs, recovery).
- Add a follow-up appointment to the phone calendar.
- Finish the baseline quiz.
- Improve on the post-quiz.

This is the piece that makes it "gamification of the discharge process" rather
than "a quiz with a score." (Read-section and calendar stars are the open build
item; the quiz-side rewards ship today.)

### 3.3 Levels - long-horizon competence
Eight XP thresholds (100 -> 1900). Levels only ever go up; there is no demotion.
Purpose: a returning patient sees accumulated progress, not a reset.

### 3.4 Mastery badges - competence per topic
Per comprehension domain, a three-step ladder: Keep learning / Almost there /
Mastered. A badge, once earned, never downgrades. This targets SDT's
competence need directly and tells a care team where understanding is solid.

### 3.5 Personal bests + welcome-back - autonomy, not comparison
Best score, biggest comprehension lift, quizzes completed, current level. All
self-referential; the patient competes only with their own past, never with
other patients (no leaderboards - inappropriate for a patient population).

### 3.6 Calm celebration - the anti-fatigue rule
Confetti and haptics fire **only** on an improved or perfect post-quiz, not on
every interaction. Rare celebration stays meaningful; constant celebration
becomes noise and, per the burnout evidence, drains motivation.

## 4. The "Master it" loop - competence through mastery, not pressure

After a post-quiz, any domain the patient missed triggers a focused review of
just those learning cards, then a short retake of only the missed questions.
Correct answers carry over; the retake is short and winnable. This is the
SDT competence mechanic: the patient always converges on understanding, and
never feels stuck or punished. Scoring still submits the full answer set, so
the stored comprehension delta is unaffected.

## 5. What we deliberately do NOT do

- **No timers or speed scoring.** Pressure is wrong for older or unwell users.
- **No leaderboards or social comparison.** A patient population is not a contest.
- **No streak-loss guilt.** Missing a day must never read as failure.
- **No rewards for volume.** Rewards attach to comprehension steps, not to
  taps, so the mechanic can never be farmed for empty engagement.
- **No claim that rewards drive adherence.** We report engagement and
  comprehension lift, and say exactly that.

## 6. What we measure

- Comprehension lift: pre versus post teach-back delta (the headline metric).
- Engagement: quizzes completed, sections read, mastery reached, return visits.
- We do **not** measure or claim a medication-adherence outcome this summer.

## 7. Data and privacy

All gamification state (XP, stars, levels, badges, bests) is **engagement data,
never clinical data**. On mobile it persists on-device only (SharedPreferences);
on the web fallback it is session-scoped. No reward state is tied to patient
identity, and none of it is sent to or stored with any clinical record.

## 8. Current build status

| Mechanic | Status |
|---|---|
| XP, levels, mastery badges, personal bests, calm celebration | Built (mobile + web) |
| "Master it" missed-questions retake loop | Built |
| On-device persistence of reward state | Built (mobile) |
| Stars for reading sections and adding a calendar appointment | Built (wave 2: `SectionStarStore` + calendar star) |
| Recovery Journey - milestone-trail visual over stars, mastery, and quests | Built (wave 2 as the Recovery Garden; rethemed Jul 18 2026 to `journey_widgets.dart` - unisex, age-neutral; no punishment states) |
| "First week home" quests - three named journeys over existing state | Built (wave 2: `quests.dart`; progress only counts up) |
| Daily mood check-in with rough-patch care-team nudge | Built (wave 3: `CheckinStore`, `consecutiveRoughDays`) |
| Medical matching puzzle built from the patient's own extraction | Built (wave 4: `puzzle.dart`; teach popup per match, nothing fabricated) |
| Medication reminder schedule from Agent 1 extraction | Built (feature B1: `medication_schedule.dart`; suggest-only, patient-editable) |
| Daily journey nudge - opt-in, one gentle 10am notification, no guilt copy | Built (wave 5: `ReminderService.enableGardenReminder` - legacy name; bell toggle on the journey card) |
| Mood-adaptive coach - one next step sized to today's check-in mood | Built (wave 5: `journey_coach.dart`; rough days are asked LESS, never more) |
| Named companion - emotional-ownership mechanic | **Retired Jul 18 2026** with the garden theme (read as childish/gendered); `CompanionStore` deleted, stored names/kinds orphaned harmlessly on-device |
| Bonus-unlocks-tomorrow return hook - quiz/puzzle banks today's effort, never expires | Built (wave 5: `SeedStore` - legacy seed naming kept for pref-key continuity; payoff acknowledged on next visit) |
| Scene seasons - sky shift with the real calendar, no bad-weather state | Built (wave 6: `seasonOf()` in `journey_widgets.dart`; delight only, no weather punishment) |
| "Share your journey" card - painting rendered to PNG, native share sheet | Built (wave 6: patient-initiated, composed on-device, no server) |

## Sources

- JMIR mHealth uHealth 2022, gamification/incentives for medication adherence (scoping review): ncbi.nlm.nih.gov/pmc/articles/PMC8902658/
- JMIR 2021, gamification in mental-health apps (meta-analysis, null clinical effect): ncbi.nlm.nih.gov/pmc/articles/PMC8669581/
- "From immersion to burnout", gamified health education anxiety/burnout, PMC 2025: pmc.ncbi.nlm.nih.gov/articles/PMC12913498/
- Self-Determination Theory gamification framework for adult motivation, Springer: link.springer.com/chapter/10.1007/978-3-030-20798-4_7
- eHealth autonomy/competence/relatedness in older adults (SDT), PMC: ncbi.nlm.nih.gov/pmc/articles/PMC11561439/
