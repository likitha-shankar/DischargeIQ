"""
File: dischargeiq/tests/test_review_analytics.py
Owner: Likitha Shankar
Description: Unit tests for the clinician-review gate math (Sprint 5, Task 5.1)
  in ui/review_analytics.py - per-document rollup, the median >= 4.0 gate, the
  zero-hallucination rule, and the below-gate fix-pass worklist.
Dependencies: pytest (no DB - pure functions only).
Called by: pytest default run.
"""

from ui.review_analytics import doc_rollup, gate_status


def _row(reviewer, doc, score, hallucination=False):
    return {
        "reviewer": reviewer, "doc_name": doc, "score": score,
        "hallucination": hallucination, "comments": "", "created_at": None,
    }


def test_rollup_medians_and_taint():
    scores = [
        _row("a", "doc1", 5), _row("b", "doc1", 4),
        _row("a", "doc2", 2, hallucination=True), _row("b", "doc2", 3),
    ]
    rollup = doc_rollup(scores)
    assert rollup["doc1"]["median"] == 4.5
    assert rollup["doc1"]["hallucination"] is False
    # One reviewer's flag taints the whole document (zero-tolerance gate).
    assert rollup["doc2"]["hallucination"] is True


def test_gate_passes_only_when_complete_clean_and_above_median():
    scores = [_row("a", f"doc{i}", 5) for i in range(3)]
    gate = gate_status(scores, corpus_size=3)
    assert gate["passed"] is True
    assert gate["overall_median"] == 5.0

    # Incomplete coverage: same scores, bigger corpus -> not passed.
    assert gate_status(scores, corpus_size=50)["passed"] is False

    # One hallucination anywhere fails the gate even at median 5.
    tainted = scores + [_row("b", "doc0", 5, hallucination=True)]
    gate = gate_status(tainted, corpus_size=3)
    assert gate["passed"] is False
    assert gate["hallucination_docs"] == ["doc0"]


def test_below_gate_worklist_feeds_fix_pass():
    scores = [
        _row("a", "good", 5),
        _row("a", "bad", 3), _row("b", "bad", 2),
    ]
    gate = gate_status(scores, corpus_size=2)
    assert gate["below_gate_docs"] == ["bad"]
    # Overall median over per-doc medians: median(5.0, 2.5) = 3.75 < 4.0.
    assert gate["overall_median"] == 3.75
    assert gate["passed"] is False


def test_empty_scores_yield_safe_defaults():
    gate = gate_status([], corpus_size=50)
    assert gate["docs_scored"] == 0
    assert gate["overall_median"] is None
    assert gate["passed"] is False
