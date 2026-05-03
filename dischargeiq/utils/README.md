# `utils/` — shared helpers

Cross-cutting utilities used by agents, the orchestrator, and the
FastAPI layer. Keep utilities small and side-effect-free.

## Files

- `llm_client.py` — `get_llm_client(provider)` factory. Returns an
  OpenAI-compatible client for `openrouter`, `openai`, `anthropic`,
  or `ollama` based on `LLM_PROVIDER` in `.env`. One entry point —
  do not instantiate provider SDKs directly elsewhere.
- `scorer.py` — `fk_score(text)` and `fk_check(text, threshold=6.0)`.
  Wraps `textstat` and returns an FK grade + pass flag. Does not write
  to any log file — FK logging happens inside each agent's own
  `_log_fk_score()` function.
- `extraction_scope.py` — `scope_for_agent2/3/4/5(extraction)`.
  Builds a narrowed copy of `ExtractionOutput` for each downstream agent
  so the LLM prompt only sees fields that agent is allowed to read.
  Reduces token cost and hallucination surface.
- `warnings.py` — `assess_extraction_completeness(extraction)`.
  Returns a list of human-readable warnings when Agent 1's output
  is incomplete (missing follow-ups, no restrictions, etc.).
- `logger.py` — `configure_logging()`. Sets up rotating file + console
  handlers writing to `logs/session_<ts>.log`. Call once at app
  start-up from `main.py`.
- `questions_html.py` — `build_questions_section_html(gaps)` and
  `build_copy_button_html()`. Pure HTML builder for the "Questions to
  bring to your care team" block rendered in the AI Review tab.
  HTML-escapes all user-visible content. Kept separate from
  `streamlit_app.py` to allow unit testing without the Streamlit runtime.

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
