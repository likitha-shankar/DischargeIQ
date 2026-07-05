# Task 1.4 — Model Routing and Safety Gating ✅

**Deliverable:** Gemini primary; automatic Claude failover; Vertex AI path for
real-world data; FK readability gate on every output.

**Commits / tag:** `26a761a` (failover), `b2e07b2` (Vertex) / `task-1.4-failover-vertex`

**Failover:** `LLM_FALLBACK_PROVIDER` (default anthropic). One attempt on the
fallback provider when the primary fails after its retries; fallback uses its
own default model; original error re-raised if both fail. Covers all 7 agents.
Proven in production use: Gemini rate-limited during corpus generation and
Claude finished the batch automatically.

**Vertex (dual data-mode):** `LLM_PROVIDER=vertex` serves the same Gemini
models inside a GCP project where a BAA can cover inference — required before
any real patient document. OAuth via Application Default Credentials with
auto-refresh. Synthetic mode keeps the plain API key. Switching modes is one
env var, no code change.

**FK gate:** every agent output (including quiz questions) scored via
`fk_check()` and logged to `evaluation/fk_log.csv`.

**Demo:** break GOOGLE_API_KEY → pipeline completes on Claude (log line shows
the failover); show `.env.example` vertex block.
