#!/usr/bin/env bash
#
# File: scripts/run_safety_gates.sh
# Owner: Likitha Shankar
# Description: Runs the safety-critical test suites that a bare `pytest` skips.
#   pytest.ini sets `-m "not slow"`, and every safety gate is marked slow
#   because it makes real LLM calls - so the default run reports a green
#   "171 passed" while zero safety gates have executed. This script runs them
#   deliberately: Agent 3 (medication guardrails), Agent 5 (escalation
#   language, hard rule #3), and the Agent 1/2 hallucination gate.
# Usage: ./scripts/run_safety_gates.sh   (from repo root)
# Environment variables required: whichever provider key LLM_PROVIDER needs
#   (GOOGLE_API_KEY for gemini, ANTHROPIC_API_KEY for anthropic, ADC for vertex).
#   Tests skip themselves rather than fail when no key is configured.
# Edge cases: real model calls cost quota and take minutes; run on fresh quota.
#   Exits non-zero if any gate fails, so CI can consume it directly.

set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
    PYTHON="python3"
fi

echo "Running safety gates (real LLM calls - expect several minutes)."
echo "  Agent 3  - medication guardrails"
echo "  Agent 5  - escalation language, no hedging (hard rule #3)"
echo "  Agent 1/2 - hallucination gate"
echo

# -m "safety" overrides the -m "not slow" default in pytest.ini: the last -m
# wins, so these run even though every one of them is also marked slow.
"$PYTHON" -m pytest -m safety -v --tb=short

echo
echo "Safety gates PASSED. This result is only valid for the current prompts"
echo "and the provider configured in .env - re-run after changing either."
