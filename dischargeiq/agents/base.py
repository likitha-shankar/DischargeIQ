"""
agents/base.py

Shared protocol and result type for all DischargeIQ agents.

Defining a common TypedDict for agent output and a typing.Protocol for
the agent callable removes the implicit duck-typed contract that previously
existed only in comments. Callers can now type-check agent results uniformly
and pass agents as first-class values without knowing their module paths.

All agents (2-6) return AgentResult. Agent 1 (extraction) returns
ExtractionOutput and is excluded from this protocol intentionally — its
output schema is separately locked in models/extraction.py.
"""

from typing import Protocol, TypedDict, runtime_checkable


class AgentResult(TypedDict):
    """
    Standard output envelope for agents 2–5.

    Fields:
        text:     Plain-language patient-facing output for this agent.
        fk_grade: Flesch-Kincaid grade of `text` (target ≤ 6.0).
        passes:   True when fk_grade ≤ 6.0 (matches fk_check() threshold).
    """

    text: str
    fk_grade: float
    passes: bool


@runtime_checkable
class AgentCallable(Protocol):
    """
    Protocol satisfied by every agent 2–5 run function.

    Allows the orchestrator to hold a list of AgentCallable objects and call
    them uniformly rather than importing each agent function by name. Supports
    future patterns such as A/B testing agents or hot-swapping prompts without
    modifying the orchestration layer.

    Example usage in orchestrator:
        agents: list[AgentCallable] = [
            run_diagnosis_agent,
            run_medication_agent,
            run_recovery_agent,
            run_escalation_agent,
        ]

    Note: `document_id` is the only universally-required keyword arg.
    Provider/model resolution is each agent's internal responsibility.
    """

    def __call__(self, *, document_id: str, **kwargs) -> AgentResult:
        """
        Execute the agent and return a standardised AgentResult dict.

        Args:
            document_id: Source document label for FK logging and console output.
            **kwargs:    Agent-specific inputs (extraction scopes, safety_context, etc.)

        Returns:
            AgentResult with text, fk_grade, and passes fields.

        Raises:
            ValueError: If required extraction fields are missing.
            Exception:  On LLM API failure (callers wrap in asyncio.gather with
                        return_exceptions=True and treat the exception as a partial).
        """
        ...
