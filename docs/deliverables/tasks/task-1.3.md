# Task 1.3 — Supervisor/Router Agent ✅

**Deliverable:** a lightweight classifier in front of Agent 1 that tags the
document type and gates non-discharge documents before any expensive agent runs.

**Commit / tag:** `220c118` / `task-1.3-router`

**Design:** first ~2000 chars → one small LLM call → {document_type (5
diagnosis categories + unknown), confidence, should_process, reason}.
Non-fatal by contract: router errors fall back to should_process=true so a
real discharge summary is never dropped by a classifier bug. Rejection
returns a "partial" response with a human-readable reason.

**Files:** `dischargeiq/agents/router_agent.py`,
`dischargeiq/prompts/router_system_prompt.txt`, orchestrator wiring.

**Demo:** upload a resume → clean rejection message, zero downstream agent calls.
