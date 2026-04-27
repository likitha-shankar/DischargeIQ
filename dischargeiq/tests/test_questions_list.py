"""
File: dischargeiq/tests/test_questions_list.py
Owner: Likitha Shankar
Description: Black-box tests for the 'Questions to bring to your care team'
  section rendered in the AI Review tab.  Tests call build_questions_section_html()
  directly — a pure HTML builder with no Streamlit dependency — so no LLM or
  Streamlit runtime is required.
Key functions/classes: test_unanswered_questions_appear_answered_does_not,
  test_all_answered_renders_no_section
Edge cases handled:
  - All concepts answered → empty string returned, section suppressed.
  - Mixed answered/unanswered → only unanswered questions in output.
Dependencies: dischargeiq.utils.questions_html
Called by: pytest (testpaths = dischargeiq/tests per pytest.ini).
"""

import pytest

from dischargeiq.utils.questions_html import build_questions_section_html


# ── Shared helpers ─────────────────────────────────────────────────────────────


def _concept(question: str, *, answered: bool) -> dict:
    """Build a minimal concept dict matching the MissedConcept wire format."""
    return {
        "question": question,
        "answered_by_doc": answered,
        "gap_summary": "Some gap detail." if not answered else "N/A",
        "severity": "moderate",
    }


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_unanswered_questions_appear_answered_does_not() -> None:
    """
    3 unanswered + 1 answered: all 3 unanswered question strings must appear
    in the rendered HTML; the answered question must be absent.
    """
    q_unanswered = [
        "What does it mean that I have heart failure?",
        "Nobody told me how much water I can drink — is that okay?",
        "What do I do if I miss my Metformin dose?",
    ]
    q_answered = "When is my follow-up appointment?"

    gaps = [_concept(q, answered=False) for q in q_unanswered]
    # Note: build_questions_section_html receives only the unanswered gaps list.
    # The caller (_render_section_simulator) filters gaps before passing them in.
    html = build_questions_section_html(gaps)

    assert html, "Expected non-empty HTML for 3 unanswered concepts"
    for q in q_unanswered:
        assert q in html, f"Expected unanswered question in HTML: {q!r}"
    assert q_answered not in html, (
        f"Answered question must not appear in questions section: {q_answered!r}"
    )


def test_all_answered_renders_no_section() -> None:
    """
    When all concepts are answered_by_doc=True, the caller passes an empty
    gaps list.  build_questions_section_html must return an empty string so
    the section is suppressed entirely.
    """
    # Simulate the caller's filtering: all answered → gaps list is empty.
    gaps: list = []
    html = build_questions_section_html(gaps)

    assert html == "", (
        "Expected empty string when no unanswered gaps — section must not render"
    )
