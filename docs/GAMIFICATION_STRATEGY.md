# DischargeIQ - Gamification Strategy

**Author:** Likitha Shankar
**Date:** July 11, 2026 (revised 31 July 2026; learning goals added 5 August 2026)
**For:** Leap of Faith, LLC (John Trzesniak, Tanuj Pravin)
**Fulfills:** Work Plan v2, task 2.3 (gamification strategy document)

---

## The one page

Task 2.3 asks for one page. This is it; everything after is the evidence and
detail behind it.

**The mechanics.** Stars for each step of working through a discharge summary
(read a section, add the follow-up to your calendar, take the baseline quiz,
improve on the post-quiz). XP and levels for comprehension answered correctly.
A badge per domain once it is understood. Personal bests, never a leaderboard.
Three "first week home" quests over that same state, and a Recovery Journey
trail that shows it all as one picture.

**What the patient sees.** Their own progress, on their own terms: stars fill
as they read, the baseline quiz gives no feedback because it has to measure
rather than teach, the post-quiz shows before and after side by side, and
confetti fires once - on a genuine improvement. Missing a question offers a
retake of just that question. Missing a day costs nothing. Nothing ever
counts down, turns red, or compares them to another patient.

**The honest expectation.** Rewards can raise interest and engagement. They
are not claimed to guarantee adherence, and this project does not measure
adherence. Per John's eMed experience and the published evidence, engagement
effects are real and clinical-outcome claims are not supported. What is
reported is the comprehension delta between the pre and post quiz, and
engagement counts alongside it - stated as what they are.

**The design constraint that shaped all of it.** The population includes
people who are older, in pain, or frightened. So: no timers, no speed
pressure, no streak punishment, no loss states, and a rough day on the mood
check-in results in being asked to do less, not more.

---

## 0. Learning goals - gamifying what the patient asked for

Added 5 August 2026, from clinical review: *define a rubric, ask the patient
what they want to learn, and gamify that.* It reorders everything below.

**The ask.** After the first analysis, the patient is asked one question -
*what do you most want to understand?* - and picks from the five discharge
topics, each phrased as a reason rather than a category ("What each pill is
for, and when to take it"). Choosing nothing is a valid answer, remembered as
one, and the journey simply keeps its default order.

**The rubric.** For each chosen topic the patient rates themselves on a
four-rung teach-back ladder, before reading and again after:

| Rung | Wording |
|---|---|
| 0 | I have not really understood this part |
| 1 | I get the general idea, but not the details |
| 2 | I could explain this to someone at home |
| 3 | I could teach this, and act on it without checking |

Rung 2 is the bar, because "could you explain it to someone at home" is what
teach-back actually asks at the bedside. Rung 3 is aspirational and is never
required to complete anything.

**What "gamify that" means concretely.** A goal is not a stored preference; it
changes what the app does next:

- A **personal goal quest** sits above the app's own three quests. A quest the
  patient chose outranks three the product chose for them.
- **Reading order** follows the goals - "Understand it" names a chosen topic
  as the next step, not whichever section happens to come first.
- The **mood-adaptive coach** points at a chosen topic first, with one
  exception: a rough day still asks for nothing. The mood rule outranks the
  goal rule, always.
- The **goal strip** on the journey card shows each goal's state and its
  rubric movement.

**What is measured.** The before/after change in the patient's own rating, per
topic. It is deliberately their judgement, not a score the app assigns, and it
sits alongside the quiz delta rather than replacing it - one is
self-perception, the other is demonstrated recall, and the gap between them is
itself interesting.

**A drop is reported, not hidden.** A patient who rates themselves lower after
reading has discovered they understood less than they thought. That is a real
and useful result, so negative movement is never clamped to zero.

**Scope, honestly.** This measures self-reported understanding of chosen
topics. It is not a clinical outcome and is not claimed as one.

---

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
than "a quiz with a score." All of it is built: section stars are scoped per
document, so a patient with several summaries earns them separately rather
than once across everything.

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

## 5. What the patient sees, step by step

The plan asks for this explicitly, so it is written as the patient's path
rather than as a feature list.

| Step | What they do | What they see |
|---|---|---|
| 1 | Open the app | Their own name, or the person they care for, in the header. Level and XP so far. Nothing to dismiss |
| 2 | Upload or scan a summary | Progress while the pipeline runs. No reward yet - nothing has been understood |
| 3 | Read a section (diagnosis, medications, appointments, warning signs, recovery) | A star fills for that section on the Recovery Journey trail. Five sections, five stars |
| 4 | Add a follow-up appointment to their phone calendar | The action star. This is the one reward tied to doing something outside the app |
| 5 | Take the baseline quiz | A star for finishing. **No answers, no hints, no score feedback** - it measures, it must not teach |
| 6 | Work through the learning cards | Nothing to collect here. Reading is not scored, so it cannot be farmed |
| 7 | Take the post-quiz | Before score, after score, and the difference side by side. XP per correct answer, plus the round bonus |
| 8 | Improve, or master a domain | A quiet badge on that domain. Confetti fires here and only here |
| 9 | Miss something | "Master it" offers just the missed questions. No penalty, no lost progress, no timer |
| 10 | Come back tomorrow | Progress is where they left it, plus whatever the last visit banked. Levels never fall |

Two things a patient never sees: a leaderboard, and a red or empty state that
reads as failure. Progress only counts up.

## 6. What we deliberately do NOT do

- **No timers or speed scoring.** Pressure is wrong for older or unwell users.
- **No leaderboards or social comparison.** A patient population is not a contest.
- **No streak-loss guilt.** Missing a day must never read as failure.
- **No rewards for volume.** Rewards attach to comprehension steps, not to
  taps, so the mechanic can never be farmed for empty engagement.
- **No claim that rewards drive adherence.** We report engagement and
  comprehension lift, and say exactly that.

## 7. What we measure

- Comprehension lift: pre versus post teach-back delta (the headline metric).
- Engagement: quizzes completed, sections read, mastery reached, return visits.
- We do **not** measure or claim a medication-adherence outcome this summer.

## 8. Data and privacy

All gamification state (XP, stars, levels, badges, bests) is **engagement data,
never clinical data**. On mobile it persists on-device only (SharedPreferences);
on the web fallback it is session-scoped. No reward state is tied to patient
identity, and none of it is sent to or stored with any clinical record.

## 9. Current build status

Everything below is built and running on device as of 31 July 2026.

| Mechanic | What it does |
|---|---|
| XP, levels, mastery badges, personal bests | Progress signal and per-domain competence; never downgrades |
| "Master it" retake loop | Re-asks only the missed questions, with no penalty |
| Section stars + calendar action star | The discharge-process layer; scoped per document so several summaries do not share one set |
| Recovery Journey trail | The visual over stars, mastery, and quests. Weeks read as colour-coded chapters, and only the current one is open |
| "First week home" quests | Three named arcs - Understand it, Act on it, Own it - over state that already exists. Progress only counts up |
| Daily mood check-in | Gentle, optional. Several rough days in a row surfaces a care-team nudge, never a scolding |
| Mood-adaptive coach | One next step sized to today's check-in. A rough day is asked LESS, never more |
| Matching puzzle | Built from the patient's own extraction, never from generic content, so nothing is fabricated |
| Medication reminder schedule | Suggested from Agent 1's extraction, patient-editable, local notifications only |
| Opt-in daily nudge | One notification, no guilt copy, off by default |
| Return hook | Effort today is acknowledged on the next visit. It never expires, so missing a day costs nothing |
| Seasons | The scene shifts with the real calendar. Delight only - there is no bad-weather or neglected state |
| Share card | Patient-initiated, composed on-device, rendered to PNG. Nothing leaves the phone unless they choose to share it |
| Calm celebration | Confetti and haptics on an improved or perfect post-quiz, and nowhere else |

### Retired

**Recovery Garden and the named companion (retired 18 July 2026).** The garden
metaphor and its named companion pet were built and then removed: on review
they read as childish and gendered for a population that includes older adults
recovering from surgery. The same underlying state - stars, mastery, quests -
was rethemed as the Recovery Journey, which is unisex and age-neutral. No
mechanic was lost; only the metaphor changed. `CompanionStore` is deleted, and
any names stored on a device before that date are orphaned harmlessly.

Two legacy identifiers survive in code (`enableGardenReminder`, `SeedStore`)
purely to keep SharedPreferences keys stable across the retheme. Renaming them
would silently reset returning patients' progress, which is a worse outcome
than an inelegant name.

## Sources

- JMIR mHealth uHealth 2022, gamification/incentives for medication adherence (scoping review): ncbi.nlm.nih.gov/pmc/articles/PMC8902658/
- JMIR 2021, gamification in mental-health apps (meta-analysis, null clinical effect): ncbi.nlm.nih.gov/pmc/articles/PMC8669581/
- "From immersion to burnout", gamified health education anxiety/burnout, PMC 2025: pmc.ncbi.nlm.nih.gov/articles/PMC12913498/
- Self-Determination Theory gamification framework for adult motivation, Springer: link.springer.com/chapter/10.1007/978-3-030-20798-4_7
- eHealth autonomy/competence/relatedness in older adults (SDT), PMC: ncbi.nlm.nih.gov/pmc/articles/PMC11561439/
