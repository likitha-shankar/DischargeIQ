# Gamification briefing - for Ken

**Context:** Frank and Steve are connecting DischargeIQ with Ken, a
gamification expert. This is the pre-read so the conversation starts at the
design questions rather than at a product tour.

**What DischargeIQ is, in one paragraph:** a patient uploads their hospital
discharge document. Six AI agents rewrite it at a sixth-grade reading level -
what happened, what each medication is for, what recovery looks like week by
week, which symptoms mean call 911 - and a teach-back quiz measures what the
patient actually retained. The gamification layer sits over that: it exists to
get someone to finish reading a document they would otherwise put in a drawer.

**Full detail:** `docs/GAMIFICATION_STRATEGY.md`. This brief is the summary
plus the specific questions we want Ken to answer.

---

## 1. The population, because it drives every constraint

Not a consumer audience. Someone who was discharged from hospital in the last
few days: often older, frequently in pain, on new medication, sometimes
frightened, and possibly reading with a family member. Some are recovering
from surgery. Some are managing heart failure or COPD.

That population is why the usual engagement playbook is mostly unavailable to
us - see section 3.

**Baseline problem:** measured comprehension of discharge instructions sits
around 13%. Our target after using the app is 50-70%, measured as a before/
after quiz delta on the patient's own document.

---

## 2. What is built and running today

| Mechanic | Behavior |
|---|---|
| **Section stars** | One per section read, plus one for adding the follow-up appointment to the calendar. Scoped per document |
| **Recovery Journey trail** | The visual over everything else. Weeks are colour-coded chapters; only the current one is open |
| **Quests** | Three named arcs - Understand it, Act on it, Own it - built over state that already exists. Progress only counts up |
| **XP, levels, mastery badges** | Progress signal and per-topic competence. Never downgrade |
| **"Master it" retake** | Re-asks only the questions missed, no penalty |
| **Teach-back quiz** | Five non-leading MCQs from the patient's own document, before and after reading |
| **Matching puzzle** | Built from the patient's own extracted medications and warning signs, never generic content. Three difficulty tiers |
| **Daily mood check-in** | Optional. Several rough days surfaces a care-team nudge, never a scolding |
| **Mood-adaptive coach** | One next step, sized to today's check-in. A rough day is asked *less*, never more |
| **Medication reminders** | Suggested from the extraction, patient-editable, local notifications only |
| **Return hook** | Effort is acknowledged on the next visit. Never expires |
| **Share card** | Patient-initiated, composed on-device |
| **Calm celebration** | Confetti and haptics on an improved or perfect post-quiz, nowhere else |

All reward state is engagement data, stored on-device, never tied to clinical
records.

---

## 3. What we deliberately refused to build

This is where we most want to be challenged, because each of these costs
engagement and we chose it anyway:

- **No timers or speed scoring.** Pressure is wrong for someone unwell.
- **No leaderboards or social comparison.** A patient population is not a
  contest.
- **No streak-loss.** Missing a day must never read as failure. This is the
  big one - streaks are the single most reliable retention mechanic in
  consumer apps and we will not use them.
- **Nothing turns red or decays.** No wilting, no neglect state, no guilt.
- **No rewards for volume.** Rewards attach to comprehension steps, not taps,
  so the mechanic cannot be farmed.
- **No claim that rewards drive adherence.** We report engagement and
  comprehension lift, and say exactly that.

**One thing we already got wrong and fixed:** the first build used a Recovery
Garden with a named companion pet. On review it read as childish and gendered
for a population that includes 70-year-olds recovering from hip replacement.
We retired the metaphor and rethemed the same underlying mechanics as the
Recovery Journey. No mechanic was lost - only the metaphor changed. Useful
signal about how narrow the tonal band is here.

---

## 4. What we want from Ken

Specific questions, roughly in priority order.

1. **Does a rewards layer belong here at all?** We are asking sincerely. The
   honest case against: someone who just got out of hospital may find any
   gamification trivializing. If the answer is "not this population", we would
   rather hear it now.

2. **Without streaks, what actually drives return visits?** Our return hook is
   deliberately toothless - it acknowledges past effort and costs nothing to
   miss. That is kind, and probably weak. What replaces streak pressure for a
   population where pressure is off the table?

3. **Is the engagement window even multi-day?** Recovery attention may be
   front-loaded into 48 hours. If so, a long-arc quest system is the wrong
   shape and we should optimize the first session instead.

4. **Where is the line between encouraging and pressuring?** We drew it by
   instinct. Ken has presumably seen it drawn with evidence.

5. **Are the three quest arcs the right decomposition?** Understand it / Act
   on it / Own it. Or is a single clear next action stronger than three
   parallel tracks?

6. **Is the mood check-in a gamification mechanic or a clinical one?** It
   drives what the coach asks of the patient today, which makes it feel like
   both, and that ambiguity may be a design smell.

7. **What would you measure that we are not?** We currently track
   comprehension lift, quizzes completed, sections read, mastery reached, and
   return visits.

---

## 5. Constraints worth knowing before suggesting anything

- **Solo developer**, 13-week program, currently week 4.
- **Flutter mobile is the primary product**; the Streamlit web app is a demo
  fallback.
- **No social layer is possible.** Health data, no accounts, nothing leaves
  the device. Anything requiring other users is out.
- **All content is derived from the patient's own document.** Nothing may be
  fabricated, including puzzle and quiz content, which limits how much
  authored game content can exist.
- **Accessibility is not negotiable.** Large text, read-aloud, and colour that
  survives low vision.

---

## 6. What a good session looks like

We leave with a clear answer on question 1, one concrete mechanic to add or
remove, and an honest read on whether the no-streaks constraint is
survivable or fatal for retention.
