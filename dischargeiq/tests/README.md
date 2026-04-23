# `tests/` — integration + hallucination suite

End-to-end tests that run the full pipeline against real PDF fixtures
and audit the output with an LLM judge. These are the gating tests
for prompt and agent changes.

## Files

- `test_integration_hallucination.py` — 8-case suite. For each
  fixture: runs the pipeline, audits Agent 1 extraction against the
  known-truth JSON, runs the LLM judge on the Agent 2 explanation to
  detect fabrication. Gate: 0 hallucinations, ≤ 3 omissions total.
- `fixtures/` — PDF inputs. See `fixtures/README.md`.

## Running

```bash
# 8-case hallucination suite (primary gate)
python dischargeiq/tests/test_integration_hallucination.py

# Single fixture, ad-hoc:
python -c "
from dotenv import load_dotenv; load_dotenv()
from dischargeiq.pipeline.orchestrator import run_pipeline
r = run_pipeline('dischargeiq/tests/fixtures/chf_narrative.pdf')
print(r.pipeline_status, r.fk_scores)
"
```

## Passing bar

- 8/8 cases PASS
- 0 hallucinations (hard gate)
- ≤ 3 omissions across all cases (soft gate)

Before merging any agent or prompt change, the full suite must PASS.
