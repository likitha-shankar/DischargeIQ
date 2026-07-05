"""
File: dischargeiq/tests/test_quiz.py
Owner: Likitha Shankar
Description: Deterministic tests for the teach-back quiz loop (Sprint 3, Task 3.1) -
  quiz agent JSON parsing/validation, pure scoring logic, and both /quiz endpoints
  via TestClient with the LLM mocked. No network I/O.
Key functions/classes: test_* functions
Dependencies: pytest, fastapi.testclient, dischargeiq.agents.quiz_agent,
  dischargeiq.services.quiz, dischargeiq.main
Called by: pytest default run (not marked slow).
"""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dischargeiq.agents import quiz_agent
from dischargeiq.main import app
from dischargeiq.services.quiz import score_quiz

_client = TestClient(app)

# One valid LLM response used across tests - 5 questions, one per domain.
_VALID_LLM_RESPONSE = json.dumps([
    {
        "question": f"Question about {domain}?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_index": i % 4,
        "domain": domain,
        "explanation": "Because the document says so.",
    }
    for i, domain in enumerate(
        ["diagnosis", "medications", "follow_up", "activity", "red_flags"]
    )
])

_EXTRACTION = {
    "primary_diagnosis": "Heart failure",
    "medications": [{"name": "Furosemide", "dose": "40mg", "frequency": "daily"}],
    "red_flag_symptoms": ["weight gain over 3 lbs in a day"],
}


# ── Quiz agent parsing ──────────────────────────────────────────────────────────


def test_quiz_agent_parses_valid_response():
    """5 valid questions parse into a QuizSet with FK metadata."""
    with patch.object(quiz_agent, "call_chat_with_fallback", return_value=_VALID_LLM_RESPONSE), \
         patch.object(quiz_agent, "get_llm_client", return_value=(None, "test-model")):
        quiz_set = quiz_agent.run_quiz_agent(_EXTRACTION, "sess-1")
    assert len(quiz_set.questions) == 5
    assert {q.domain for q in quiz_set.questions} == {
        "diagnosis", "medications", "follow_up", "activity", "red_flags"
    }
    assert isinstance(quiz_set.fk_grade, float)


def test_quiz_agent_strips_markdown_fences():
    """LLM wrapping the JSON in ```json fences still parses."""
    fenced = f"```json\n{_VALID_LLM_RESPONSE}\n```"
    with patch.object(quiz_agent, "call_chat_with_fallback", return_value=fenced), \
         patch.object(quiz_agent, "get_llm_client", return_value=(None, "test-model")):
        quiz_set = quiz_agent.run_quiz_agent(_EXTRACTION, "sess-2")
    assert len(quiz_set.questions) == 5


def test_quiz_agent_drops_invalid_question_keeps_rest():
    """One malformed question (3 options) is dropped; the other 4 survive."""
    items = json.loads(_VALID_LLM_RESPONSE)
    items[2]["options"] = ["only", "three", "options"]
    with patch.object(quiz_agent, "call_chat_with_fallback", return_value=json.dumps(items)), \
         patch.object(quiz_agent, "get_llm_client", return_value=(None, "test-model")):
        quiz_set = quiz_agent.run_quiz_agent(_EXTRACTION, "sess-3")
    assert len(quiz_set.questions) == 4


def test_quiz_agent_raises_on_garbage_json():
    """Unparseable output raises ValueError (route maps to 502)."""
    with patch.object(quiz_agent, "call_chat_with_fallback", return_value="not json at all"), \
         patch.object(quiz_agent, "get_llm_client", return_value=(None, "test-model")):
        with pytest.raises(ValueError, match="unparseable JSON"):
            quiz_agent.run_quiz_agent(_EXTRACTION, "sess-4")


def test_quiz_agent_raises_on_empty_extraction():
    """No quiz-relevant fields → ValueError before any LLM call."""
    with pytest.raises(ValueError, match="populated extraction field"):
        quiz_agent.run_quiz_agent({}, "sess-5")


# ── Scoring logic ───────────────────────────────────────────────────────────────


_KEYS = [
    {"domain": "diagnosis", "correct_index": 0},
    {"domain": "medications", "correct_index": 1},
    {"domain": "medications", "correct_index": 2},
    {"domain": "red_flags", "correct_index": 3},
]


def test_score_quiz_full_marks():
    result = score_quiz("s", "pre", _KEYS, [0, 1, 2, 3])
    assert result.score == 4
    assert result.percent == 100.0
    assert result.failed_domains == []


def test_score_quiz_partial_with_domain_breakdown():
    # One medications question wrong, skipped red_flags (-1).
    result = score_quiz("s", "post", _KEYS, [0, 1, 0, -1])
    assert result.score == 2
    assert result.percent == 50.0
    assert result.domain_scores["medications"] == {"correct": 1, "total": 2}
    assert set(result.failed_domains) == {"medications", "red_flags"}


def test_score_quiz_length_mismatch_raises():
    with pytest.raises(ValueError, match="does not match"):
        score_quiz("s", "pre", _KEYS, [0, 1])


# ── Endpoints ───────────────────────────────────────────────────────────────────


def test_quiz_generate_endpoint():
    """POST /quiz/generate returns the question set from the (mocked) agent."""
    with patch.object(quiz_agent, "call_chat_with_fallback", return_value=_VALID_LLM_RESPONSE), \
         patch.object(quiz_agent, "get_llm_client", return_value=(None, "test-model")):
        resp = _client.post(
            "/quiz/generate",
            json={"session_id": "sess-api-1", "extraction": _EXTRACTION},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "sess-api-1"
    assert len(body["questions"]) == 5
    assert all(len(q["options"]) == 4 for q in body["questions"])


def test_quiz_generate_endpoint_empty_extraction_422():
    resp = _client.post(
        "/quiz/generate", json={"session_id": "sess-api-2", "extraction": {}}
    )
    assert resp.status_code == 422


def test_quiz_score_endpoint_pre_and_post():
    """Scoring works end to end; delta is None without a database."""
    keys = [{"domain": k["domain"], "correct_index": k["correct_index"]} for k in _KEYS]
    pre = _client.post(
        "/quiz/score",
        json={"session_id": "sess-api-3", "phase": "pre", "question_keys": keys,
              "answers": [0, 0, 0, 0]},
    )
    assert pre.status_code == 200
    assert pre.json()["score"] == 1

    post = _client.post(
        "/quiz/score",
        json={"session_id": "sess-api-3", "phase": "post", "question_keys": keys,
              "answers": [0, 1, 2, 3]},
    )
    assert post.status_code == 200
    body = post.json()
    assert body["score"] == 4
    # TestClient app has no DB pool by default → delta may be None; when a
    # real DATABASE_URL is configured the pre row above makes it 75.0.
    assert body["comprehension_delta"] in (None, 75.0)


def test_quiz_score_endpoint_mismatch_422():
    resp = _client.post(
        "/quiz/score",
        json={"session_id": "s", "phase": "pre",
              "question_keys": [{"domain": "diagnosis", "correct_index": 0}],
              "answers": [0, 1]},
    )
    assert resp.status_code == 422
