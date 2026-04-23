# `utils/` — shared helpers

Cross-cutting utilities used by agents, the orchestrator, and the
FastAPI layer. Keep utilities small and side-effect-free.

## Files

- `llm_client.py` — `get_llm_client(provider)` factory. Returns an
  OpenAI-compatible client for `openrouter`, `openai`, `anthropic`,
  or `ollama` based on `LLM_PROVIDER` in `.env`. One entry point —
  do not instantiate provider SDKs directly elsewhere.
- `scorer.py` — `fk_score(text)` and `fk_check(text, threshold=6.0)`.
  Wraps `textstat` and appends each Agent 2 score to
  `evaluation/fk_log.csv`.
- `warnings.py` — `assess_extraction_completeness(extraction)`.
  Returns a list of human-readable warnings when Agent 1's output
  is incomplete (missing follow-ups, no restrictions, etc.).
- `logger.py` — `configure_logging()`. Sets up rotating file + console
  handlers writing to `logs/session_<ts>.log`. Call once at app
  start-up from `main.py`.

## Using

```python
from dischargeiq.utils.llm_client import get_llm_client
from dischargeiq.utils.scorer     import fk_check
from dischargeiq.utils.warnings   import assess_extraction_completeness
from dischargeiq.utils.logger     import configure_logging
```

## Adding a helper

Keep it pure (no global state), under 40 lines per function, with a
docstring and type hints. If it has external dependencies, wire them
through the LLM client or a passed-in argument — do not import
provider SDKs here.
