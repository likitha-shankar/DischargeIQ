# Task 3.5 - Prompt Tuning Against Tester Failures ◑

**Deliverable:** prompt tuning against the domains real testers failed.

**Status:** the tuning pipeline is built and two real defects have been found
and fixed - but from CORPUS measurement, not from tester data, because there
are no testers yet (task 2.6).

## What was tuned, and what found it

Both defects were found by the full-corpus accuracy run, not by a person.

**Invented numeric thresholds.** Fever limits and rules like "call 911 if
your heart rate is over 100" appeared in patient-facing output without being
in the patient's document. On a 10-document verification set, documents
carrying an invented value went from **8/10 to 0/10**.

That fix took three attempts, and the first two shipped wrong:

1. Enumerating forbidden numbers in the prompt. The model produced 100.4 on
   a neonatal document instead.
2. Permitting only 101 F. Clinically wrong for infants, where 100.4 is the
   correct threshold.
3. Removing every number from the prompt, including the ones inside the tier
   list and the worked example. This worked.

**The lesson, which generalises:** a rule saying "do not" loses to an example
showing "how". Every worked example in a prompt is training data.

**Degenerate escalation explanations.** Agent 5 sometimes emitted tier
entries whose explanations said nothing. It now detects that and retries,
rejecting the retry if it is still degenerate, is missing CALL 911, or has
fewer bullets than the first attempt (`5a19e8e`).

## What is still owed

Tuning against the domains REAL TESTERS fail. The evidence pipeline for it
shipped (`evaluation/quiz_gap_report.py`, `aef022a`) and produces per-domain
miss rates from `quiz_scores`. It has no data to run on.

**Do not report this task as complete without saying which tuning is meant.**
The plan's wording is specifically about tester-driven tuning, and a reader
comparing planned against delivered will check that wording.
