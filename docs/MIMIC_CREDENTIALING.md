# MIMIC-IV-Note credentialing

How to get access to real de-identified hospital discharge summaries, and the
constraints that come with them.

**Status:** not started. Verified against PhysioNet 2026-07-29.

## Why bother

`test-data/mtsamples/` (106 docs) is real de-identified transcription work and
is enough for formatting robustness. It is not enough for an accuracy claim:
the samples are curated teaching examples, not a representative draw from a
hospital population.

[MIMIC-IV-Note v2.2](https://physionet.org/content/mimic-iv-note/2.2/) is
331,794 de-identified discharge summaries from 145,915 patients at Beth Israel
Deaconess Medical Center. That is the dataset an evaluation claim can rest on.

Lead time is ~2 weeks. Start it before it blocks a gate.

## The five steps

### 1. Register on PhysioNet

https://physionet.org/register/

Use the `@hawk.illinoistech.edu` address, not a personal one. PhysioNet
explicitly says an academic email or an institution-linked ORCID speeds up
review. A gmail address is the single most common cause of a slow application.

### 2. CITI training

This is the part with the gotchas. All four matter.

1. Register at https://about.citiprogram.org/ and affiliate with
   **"Massachusetts Institute of Technology Affiliates"**. Not Illinois Tech.
   This affiliation exists specifically so non-MIT people can take the course
   free.
2. Complete **both** required modules:
   - "Data or Specimens Only Research"
   - "Conflicts of Interest"
3. On the enrollment questionnaire, answer questions 1, 2, and 3, and answer
   **Yes** to question 5 (the conflicts-of-interest question). Answering No
   there skips the module you need.
4. Download the **training report**, not the completion certificate. They are
   different documents and PhysioNet rejects the certificate. Get it from
   Records → "View-Print-Share" → Completion Report.

Budget a few hours. It is self-paced multiple choice.

Reference: https://physionet.org/about/citi-course/

### 3. Credentialing application

https://physionet.org/settings/credentialing/

Upload the CITI training report. You will be asked for a **reference** — for a
student that is a supervisor or faculty member, so Tanuj or the CS 595
instructor. Tell whoever you name that
`credentialing@physionet.org` will email them and that the application stalls
until they reply. An unanswered reference email is the second most common
cause of delay.

Review takes several days to one week of business days.

### 4. Sign the data use agreement

Once credentialed, open the MIMIC-IV-Note project page and sign the DUA. Access
is per-project — being credentialed is not the same as having signed for this
specific dataset.

### 5. Download

Notes come as compressed CSV, not PDF. `discharge.csv.gz` is the file that
matters. Rendering a sample of it to PDF is a small script — the existing
`_text_to_pdf` in `scripts/generate_synthetic_corpus.py` already does the
rendering, same as `scripts/build_mtsamples_corpus.py` does for MTSamples.

## The constraint that affects our architecture

**This is stricter than it first appears. Read it before wiring anything up.**

The PhysioNet Credentialed DUA prohibits sharing the data with third parties,
and PhysioNet states this explicitly includes sending it through third-party
APIs or using it on online platforms.

Their guidance
([Use of MIMIC Data with Large Language Models and Online Services](https://physionet.org/news/post/llm-responsible-use/)):

- Locally deployed LLMs are the recommended approach — full control of the data.
- If a cloud service is used, the researcher must verify **zero data retention,
  no use of data for training, and no human review** — and must re-check,
  because provider policies change without notice.
- PhysioNet **names no approved provider**. Quoting them directly: they "cannot
  verify the data practices of external services and does not endorse or
  recommend specific platforms."
- They warn that a vendor's claimed zero-retention may still be undercut by
  internal logging or caching.

### What this means for DischargeIQ concretely

- The **default config would violate the DUA.** `LLM_PROVIDER=gemini` with
  `GOOGLE_API_KEY` is the public Gemini API — a third-party API call. MIMIC
  notes must never run through it.
- The **Vertex path is the only defensible one**, but it is defensible because
  *we* document a BAA with zero retention and no human review — not because
  PhysioNet blesses it. They bless nothing. Earlier I described Vertex as "the
  path that complies"; that overstated it. The compliance burden is ours to
  evidence and keep re-checking.
- `LLM_FALLBACK_PROVIDER` is a live hazard. It defaults to `anthropic`
  (`llm_client.py:363`), so on a Vertex failure the pipeline reaches for a
  second third-party API on its own — a DUA violation triggered by nothing more
  than a timeout. Worse: a 429 from the primary starts a process-local cooldown
  that routes calls **straight** to the fallback with no further attempt on the
  primary (`llm_client.py:8-10`). Under quota pressure that is not one leaked
  note, it is a sustained stream of them. Set `LLM_FALLBACK_PROVIDER=none` for
  any MIMIC run.
- A local model via `OLLAMA_BASE_URL` is the zero-risk option and is worth
  considering for the accuracy sweep specifically, where latency does not
  matter.

Worth building before the data lands: a guard that refuses to run when the
input is MIMIC-derived and the provider is not `vertex` or `ollama`. Cheaper
than trusting an env var to be right at 2am.

## Also gated, same DUA

If MIMIC-IV-Note gets approved, these need no additional application:

- [MedDec](https://physionet.org/content/meddec/1.0.0/) — medical decisions
  annotated on MIMIC-III discharge summaries.
- [MIMIC-IV-Ext-BHC](https://physionet.org/content/labelled-notes-hospital-course/1.2.0/)
  — labeled notes for hospital course summarization. Close to what Agent 2 does.

## Checklist

- [ ] Register with `@hawk.illinoistech.edu`
- [ ] CITI: MIT Affiliates, both modules, Yes to Q5
- [ ] Download training **report**
- [ ] Submit credentialing application
- [ ] Warn the reference that PhysioNet will email them
- [ ] Sign MIMIC-IV-Note DUA
- [ ] Confirm Vertex zero-retention + BAA in writing before first run
- [ ] Set `LLM_FALLBACK_PROVIDER=none` for MIMIC runs
