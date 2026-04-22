# `prompts/` — system prompts

One plain-text file per agent. Loaded at import time by the
corresponding `agents/*.py` module. Edit these to change behavior —
do not hard-code prompt text in Python.

## Files

- `agent1_system_prompt.txt` — Agent 1 (extraction). Strict
  JSON-only output matching `ExtractionOutput`.
- `agent2_system_prompt.txt` — Agent 2 (diagnosis). Reading-level
  rules, NO INVENTED NUMBERS rule.
- `agent3_system_prompt.txt` — Agent 3 (medications). Sprint 2.
- `agent4_system_prompt.txt` — Agent 4 (recovery). Sprint 2.
- `agent5_system_prompt.txt` — Agent 5 (escalation). Sprint 2.
- `llm_judge_prompt.txt` — Judge prompt used by the hallucination
  test suite to audit Agent 2 output for fabrication.

## Editing

1. Change the text. Do not change the prompt filename — agent modules
   reference it directly.
2. Re-run the relevant test to confirm no regression:
   ```bash
   python dischargeiq/tests/test_integration_hallucination.py
   ```
3. Target: FK ≤ 6.0 on every Agent 2 explanation, 0 hallucinations
   on the full 8-case suite.
