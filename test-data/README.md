# Test Data

Three corpora, kept separate on purpose. Nothing here is a real patient record.

## `*.pdf` at the top level (committed)

Three synthetic discharge summaries, one per common diagnosis:
`heart_failure_01`, `copd_01`, `hip_replacement_01`.

These are the documents `scripts/build_beta_kit.sh` ships to beta testers, and
`heart_failure_01.pdf` is the fixture `dischargeiq/tests/test_ingest.py` parses.
Do not delete or rename them without updating both.

Regenerate more with `scripts/generate_synthetic_corpus.py`. The larger 50-doc
generated corpus that used to live in `test-data/synthetic/` was removed once
the MTSamples corpus below replaced it as the realism benchmark; the generator
script is still there if it is ever needed again.

## `mtsamples/` (gitignored, 106 documents)

Real de-identified discharge summaries from
[MTSamples](https://www.mtsamples.com/site/pages/browse.asp?type=89-Discharge+Summary),
fetched via a community CSV mirror because the site blocks automated clients.

These are transcriptions of actual dictated medical work with identifiers
removed. They are the realism benchmark: dictated narrative, no section
headers, missing discharge fields, pediatric patients. Expect
`complete_with_warnings` on many of them, which is correct behaviour rather
than a regression.

Gitignored because the content is third-party sourced. Rebuild with:

```
python3 scripts/build_mtsamples_corpus.py
```

`corpus_index.json` maps each PDF back to its MTSamples sample name.

## `stress-test/` (committed)

Adversarial fixtures, not discharge documents. Used by
`dischargeiq/tests/test_agent5_safety.py`, `test_all_corpus_smoke.py`, and the
runners under `scripts/stress/`. Leave these alone.

## Data under a use agreement

MIMIC-IV-Note and other PhysioNet datasets must NEVER be committed here, and
must never reach a third-party LLM API. See `docs/MIMIC_CREDENTIALING.md` and
the `RESTRICTED_DATA_MODE` gate in `dischargeiq/utils/llm_client.py`.
