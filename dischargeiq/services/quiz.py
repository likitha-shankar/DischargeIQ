"""
File: dischargeiq/services/quiz.py
Owner: Likitha Shankar
Description: Pure scoring logic for the teach-back quiz (Sprint 3, Task 3.1) -
  computes score, per-domain breakdown, and failed domains from a question set
  and the patient's answers. No I/O here: the route layer handles persistence
  and the comprehension delta lookup.
Key functions/classes: score_quiz
Dependencies: dischargeiq.models.quiz only.
Called by: dischargeiq.api.routes.quiz, dischargeiq.tests.test_quiz
"""

from dischargeiq.models.quiz import QuizScoreResult


def score_quiz(
    session_id: str,
    phase: str,
    question_keys: list[dict],
    answers: list[int],
) -> QuizScoreResult:
    """
    Score one quiz phase.

    Data contract (integration point with the clients): question_keys is the
    minimal grading key - [{"domain": str, "correct_index": int}, ...] in the
    same order the questions were presented. answers is the patient's chosen
    0-based option index per question, -1 (or out of range) meaning skipped.

    Args:
        session_id: Session the quiz belongs to.
        phase: "pre" or "post" (validated by the request schema upstream).
        question_keys: Grading key, one entry per question.
        answers: Patient's selections, same length as question_keys.

    Returns:
        QuizScoreResult: score, percent, per-domain breakdown, failed domains.
        comprehension_delta is left None - the route fills it for post phases.

    Raises:
        ValueError: If answers and question_keys lengths differ, or the key
                    is empty (nothing to score).
    """
    if not question_keys:
        raise ValueError(f"Empty question key for session '{session_id}' - nothing to score.")
    if len(answers) != len(question_keys):
        raise ValueError(
            f"Answer count ({len(answers)}) does not match question count "
            f"({len(question_keys)}) for session '{session_id}'."
        )

    score = 0
    domain_scores: dict[str, dict[str, int]] = {}
    for key, answer in zip(question_keys, answers):
        domain = key["domain"]
        bucket = domain_scores.setdefault(domain, {"correct": 0, "total": 0})
        bucket["total"] += 1
        if answer == key["correct_index"]:
            score += 1
            bucket["correct"] += 1

    total = len(question_keys)
    failed = [d for d, b in domain_scores.items() if b["correct"] < b["total"]]
    return QuizScoreResult(
        session_id=session_id,
        phase=phase,  # type: ignore[arg-type]  # validated Literal upstream
        score=score,
        total=total,
        percent=round(100.0 * score / total, 1),
        domain_scores=domain_scores,
        failed_domains=failed,
    )
