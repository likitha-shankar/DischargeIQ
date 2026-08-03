# Clinician interview guide

**For:** the first conversation with a non-technical clinician
**Purpose:** two things at once - get their judgement on whether the output is
safe, and recruit them (or their colleague) as a reviewer for task 4.2.

This is a question guide, not a script. Read it once, bring the two pages of
"Section 3" and "Section 5" into the room, and let them talk.

---

## 0. How to run this, as an engineer talking to a clinician

Five rules that decide whether this meeting is worth anything.

1. **Show first, ask second.** Do not describe the product for ten minutes.
   Put a real discharge summary through it on the phone and hand them the
   phone. Every good answer you get will be a reaction to something they saw.
2. **No jargon, and no apologising for it either.** Say "the app reads the
   document and rewrites it" - not agent, pipeline, LLM, model, extraction,
   RAG, or hallucination. If they ask how it works, one sentence: *"it's the
   same kind of AI as ChatGPT, restricted so it can only use what's in the
   document in front of it."*
3. **Ask about their world before yours.** Their answers about discharge
   workflow are worth more than their opinion of your UI, and they will be
   more forthcoming once they have been asked about something they are the
   expert in.
4. **Do not defend.** When they say something is wrong, the correct response
   is "say more about that" - never "well, the reason it does that is". You
   are buying their judgement; arguing with it wastes the purchase.
5. **Ask for the failure, explicitly.** Clinicians are polite about
   prototypes. You have to give explicit permission to be harsh, more than
   once, or you will get "this is nice" and learn nothing.

**Time budget:** 45 minutes. Ten minutes of their world, fifteen showing,
fifteen on their reactions, five on logistics. If it runs short, cut the
demo, not the questions.

**Record it** (with permission) or bring someone to take notes. You cannot
run the app and write down what they say at the same time.

---

## 1. Their world - ask before showing anything

These establish what "correct" even means, and they are the questions only
someone who does discharges can answer.

1. Walk me through what actually happens when you discharge a patient. Who
   writes the summary, who hands it over, and how long does that conversation
   usually last?
2. What do you find yourself saying out loud to patients that never makes it
   onto the paper?
   *(This is the single highest-value question in the guide. Anything that is
   routinely said but never written is invisible to a system that only reads
   documents.)*
3. Which part of the discharge instructions do patients misunderstand most
   often? Where do the callbacks come from?
4. When a patient calls two days later confused, what are they usually
   confused about?
5. Who actually reads the document at home - the patient, or a family member?
   Does that change what you write?
6. What does a *bad* discharge summary look like to you? Not wrong, just bad.
7. If a patient understood only one thing from their discharge, what should it
   be?

---

## 2. Before showing the app - set the frame

Say this, roughly, in your own words:

> "This does not diagnose anything and it does not give advice. It takes the
> discharge document the patient already has and rewrites it at a sixth-grade
> reading level, then quizzes them to check what they retained. If something
> is not in their document, the app is supposed to say it does not know rather
> than fill the gap. I want you to try to catch it filling a gap."

Then ask:

8. Before you see it - what would make you refuse to let a patient use
   something like this?

Ask this *before* the demo. The answer is uncontaminated by what they are
about to see, and it tells you their real bar.

---

## 3. Screen by screen - hand them the phone

Run one real document. Let them scroll. At each screen, ask the specific
question rather than "what do you think".

### The plain-language summary

9. Read this as though you were the patient. Is anything here wrong?
10. Is anything here *right but misleading*? Technically accurate, wrong
    impression.
11. Is the reading level right, or has it been simplified past the point of
    being useful?
12. Is there anything in the original document that should have made it into
    this and did not?

### Medications

13. Check these against the source. Are the drug names, doses, and
    frequencies exactly as written?
14. The app explains *why* each medicine was prescribed. Is that explanation
    safe to give a patient, or is it overstepping?
15. Is there anything about these medicines a patient needs to be told that is
    not here?

### Warning signs - the safety-critical screen

16. The app sorts symptoms into three tiers: call 911, go to the ER today,
    call your doctor. Are any of these in the wrong tier?
17. Is anything in the "call your doctor" tier that should be higher?
    *(Wrong direction is the dangerous one. Ask it specifically.)*
18. Is anything missing that you would always tell this patient to watch for?
19. **Only 34% of real discharge documents we tested contain any warning signs
    at all.** When a document has none, the app shows generic advice - call
    911 for chest pain, trouble breathing, heavy bleeding, fainting, sudden
    weakness - clearly labelled as general advice, not from their document.
    Is showing that safer than showing nothing, or does any non-document
    content cross a line for you?

### The chatbot

20. Ask it something the document answers. Is the answer right?
21. Now ask it something the document does *not* answer. It should say it does
    not know. Does the refusal read as helpful, or as broken?
22. Ask it for advice - "should I stop taking this?" It should decline. Does
    the way it declines feel safe to you?
23. Is there a question a patient would ask that this should never attempt,
    even with a disclaimer?

### The quiz

24. The patient takes the same quiz before and after reading. The baseline
    gives no feedback at all, so it measures rather than teaches. Does that
    make sense to you as a way to check understanding?
25. Are these the five things worth checking? Diagnosis, medications,
    follow-up, activity, red flags.
26. Would a patient just out of hospital tolerate being quizzed? Is there a
    version of this that feels less like a test?

---

## 4. The judgement questions

Ask these after they have seen everything. Slow down here.

27. **Would you hand this to one of your own patients?** If not, what is the
    one thing that would change your answer?
28. What would you have to remove before you would be comfortable with a
    patient reading it unsupervised?
29. Where is the app most likely to hurt someone? Not annoy - hurt.
30. Is there anything here that a patient could reasonably read as medical
    advice, even though we never intended it that way?
31. If a patient followed this and something went wrong, what would you expect
    the failure to have been?
32. Does this create work for you, or remove it?

---

## 5. The gamification question - ask it separately and honestly

Do not bury this in the demo. Ask it as its own topic, because you genuinely
do not know the answer.

33. The app gives stars for reading each section, adding the follow-up to the
    calendar, and finishing the quiz. There are no timers, no streaks to lose,
    no leaderboards, and nothing turns red. **Does a rewards layer belong in a
    product someone uses the week they got out of hospital?**
34. Where is the line between encouraging a patient and pressuring them?
35. There is an optional daily "how are you feeling" check-in. Several rough
    days in a row surfaces a suggestion to contact their care team. Useful
    signal, or overreach?
36. Would you want to see a patient's engagement data - what they read, how
    they scored? Or does a clinician seeing that turn a comprehension tool
    into a compliance tool?
37. Is there a patient group you would *not* show this to?

---

## 6. Validating the review method itself

They are being asked to review documents later. Check the method is sane
before committing them to it.

38. We are asking reviewers to score 0 to 5 on whether the output faithfully
    represents the source, with comments required below 4. Is a 0-5 scale
    useful to you, or would pass/fail plus comments be more honest?
39. Real discharge documents are often incomplete - many have no follow-up
    date, no medication list. Our instruction to reviewers is *judge only what
    the source contained*, so the app is not marked down for a gap in the
    hospital's paperwork. Is that the right instruction?
40. We ask for a separate flag for anything invented - content in the output
    that is not in the source. Is "invented" the right word for what you would
    be looking for?
41. Is 5 to 10 documents a meaningful sample, or is that too few to say
    anything?
42. Is 10 to 15 minutes per document realistic, or optimistic?
43. Should the reviewer see the source document beside the output, or judge
    the output cold the way a patient would?
44. Is a discharge nurse or discharge coordinator the right reviewer for this,
    rather than a physician? Our assumption is yes, because it is discharge
    workflow expertise we need.

---

## 7. Logistics - close the meeting with these

45. Would you be willing to review 5 to 10 documents yourself, self-paced,
    about 1 to 2 hours total?
46. If not you, who? A discharge nurse or coordinator in your network.
47. What is the realistic turnaround - a week, a month?
48. Do you want the source documents on paper or on screen?
49. Is there anything you would need from me before you could sign off on
    something like this?
50. Can I come back to you once with follow-up questions after you review?

---

## 8. Do NOT ask

- "Do you like it?" - unanswerable and produces politeness.
- "Is the AI accurate?" - too abstract. Ask about the document in front of
  them.
- Anything about the technology stack, hosting, or which model. They do not
  care and it burns credibility.
- Anything that invites them to design the UI. You want their clinical
  judgement, not their layout preferences.
- Do not ask them to commit to a timeline in the meeting. Ask what is
  realistic, then follow up in writing.

---

## 9. What to capture, in their words

Write down verbatim, not paraphrased:

- Every instance of "I would never..." or "you can't say that"
- Anything they said patients are told verbally but never in writing
- The exact wording of anything they corrected
- Their answer to Q8 (what would make you refuse) and Q27 (would you hand
  this to a patient)
- Anything they hesitated over. Hesitation is a finding.

**After the meeting, before you forget:** write down the one thing they said
that you did not want to hear. That is usually the one worth acting on.

---

## 10. What good looks like

You leave with:

- At least one concrete thing that is wrong, in their words
- An answer to whether gamification belongs here at all
- A yes/no/maybe on them or a colleague reviewing documents
- One thing patients are told verbally that never reaches the paper - because
  that is a gap no amount of document processing will ever close, and it may
  be the most useful thing you learn all summer
