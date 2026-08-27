# Demo video script - the external one

**Action item from the LOF review, 26 Aug 2026:** *"Prepare concise and
focused demo video emphasizing key features and gamification value" (37:44)*,
*"focusing on key user-facing features rather than backend mechanics" (38:50)*,
and John's note to frame gamification **in terms of patient value and
adoption, not just feature lists** (15:10).

Structured on **NABC** (Need, Approach, Benefit, Competition), which John asked
to see in all future communications (40:00).

## This is NOT the backup recording

`DEMO_SCRIPT.md` section 9 already specifies a recording. That one is a
different artefact and both should exist:

| | Backup recording (task 4.8) | This video |
|---|---|---|
| Audience | The room, only if the live demo fails | People not in the room |
| Job | Be COMPLETE and HONEST | Be understood in one viewing |
| Length | ~6 min | **Under 3 min** |
| Shows failure paths | Yes, mandatory | No |
| Shows the dashboard | Yes | No, that is backend |
| Polish | Irrelevant | Matters |

Do not merge them. A backup that skips the rejected-document step is worthless
when you need it; an external video that spends 45 seconds on a rejection
screen loses the viewer.

## Before recording

Run the pre-flight in `DEMO_SCRIPT.md` section 0. Additionally:

- Phone on Do Not Disturb, full battery indicator, no personal notifications.
- Use `heart_failure_01.pdf`. It is a generated fixture, so no real or
  programme-provided patient data appears on screen.
- Record in one take per segment. Stitching three clean 60-second segments is
  easier than one perfect 3-minute run.

## The script

### 0:00-0:25 - NEED

*Show: the printed discharge summary, then a hand holding it.*

> "This is what a patient is handed on the way out of hospital. It is written
> for the next clinician, not for them. Around 40 to 80 percent of what
> they're told is forgotten before they get home, and nearly half of what they
> do remember, they remember wrong."

Source: Kessels 2003, `docs/CITATIONS.md`. Cite it if asked; do not put the
citation on screen.

### 0:25-1:00 - APPROACH

*Show: photograph or upload the document. Then the results appearing.*

> "They photograph it. In about ten seconds, six AI agents turn it into
> plain language: what happened, their medications, warning signs, their
> recovery week by week, and their appointments."

*Show: tap a citation chip, source page opens.*

> "Every fact links back to the line in their own document it came from. The
> app answers from their paperwork, and nothing else."

**This is the trust moment. Do not rush it.** It is also the honest answer to
"how do I know it isn't making things up".

### 1:00-1:50 - BENEFIT (the gamification segment)

Frame every second of this as **patient value**, never as a feature list.
Say what it does FOR them, not what it IS.

*Show: the quiz, then the comprehension delta banner.*

> "Reading something is not the same as understanding it. So we check. The
> patient answers a few questions before and after, and we measure the
> difference."

*Show: stars filling as tabs are read; adding a follow-up to the calendar.*

> "Progress is tracked so they finish what matters - their medications, their
> warning signs, their follow-up appointments actually in their calendar.
> There are no leaderboards and no timers. It is not a game. It is a way of
> making sure nothing important goes unread."

**Wording that matters:** "so they finish what matters" is the patient value.
"Five points across four categories" is a feature list. Use the first.

### 1:50-2:20 - Accessibility, briefly

*Show: text size increasing, then text-to-speech playing a tab.*

> "Larger text, dark mode, and every section can be read aloud - because the
> people who most need this are often the least able to sit and read."

### 2:20-2:50 - COMPETITION and the honest close

*Show: the disclaimer screen.*

> "Patient portals show the same document again. Search engines answer about
> the condition, not about this patient. This explains their own paperwork,
> in their own language, and it says plainly that it is written by AI and is
> not medical advice."

> "It surfaces the questions a patient would ask that their document does not
> answer - so a human can answer them."

**End there.** The last line is the product's actual thesis: AI finds the gap,
a person closes it.

## What to leave out, deliberately

- The clinician dashboard - backend, and not the patient story.
- The rejected-document screen - important for credibility in a live demo,
  dead weight in a 3-minute video.
- Agent names, model names, provider names, architecture.
- Accuracy percentages. They invite a question the video cannot answer and
  the numbers belong in a document where they can be qualified.
- Anything not yet built. Nothing here is aspirational; every shot is a
  screen that exists today.

## After recording

- Store it **outside this repository** - it shows analysis output. Same
  convention as the backup recording.
- Record where it lives in `docs/deliverables/sprint-4.md` under task 4.8.
- Send to Tanuj first for the weekly-demo loop before it goes further.
