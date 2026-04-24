"""
agents/patient_simulator_agent.py

Agent 6 — AI Patient Simulator. Missed-concept detection from a simulated
patient perspective (DIS-22).

run_patient_simulator_agent:
    Args:
        extraction: Agent 1 ExtractionOutput.
        document_id: Source document id for logging and fk_log.csv.
    Returns:
        PatientSimulatorOutput with missed_concepts, gap score, FK grade.
    Raises:
        ValueError: Empty LLM response, transport failure, or parse failure
            (fewer than three questions).
"""

from __future__ import annotations

import csv
import logging
import os
import re
from pathlib import Path
from typing import Literal

import textstat
from openai import APIError, OpenAI

from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.models.pipeline import MissedConcept, PatientSimulatorOutput
from dischargeiq.utils.llm_client import call_chat_with_fallback, get_llm_client

logger = logging.getLogger(__name__)

_MAX_TOKENS = 1200
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_FK_LOG_PATH = Path(__file__).parent.parent / "evaluation" / "fk_log.csv"
_FK_THRESHOLD = 8.0


def _load_system_prompt() -> str:
    """Load agent6_system_prompt.txt."""
    path = _PROMPTS_DIR / "agent6_system_prompt.txt"
    if not path.exists():
        raise FileNotFoundError(
            f"Agent 6 system prompt not found at: {path}."
        )
    return path.read_text(encoding="utf-8").strip()


def _append_bullets(lines: list[str], title: str, items: list[str]) -> None:
    """Append a titled bullet list; skip section if items is empty."""
    if not items:
        return
    lines.append(title)
    for item in items:
        lines.append(f"  - {item}")


def _med_bullet(med) -> str:
    """Format one medication line for the simulator user message."""
    parts = [med.name]
    if med.dose:
        parts.append(f"dose {med.dose}")
    if med.frequency:
        parts.append(f"frequency {med.frequency}")
    if med.status:
        parts.append(f"status {med.status}")
    return " — ".join(parts)


def _appt_bullet(appt) -> str:
    """Format one follow-up appointment line."""
    bits = []
    if appt.provider:
        bits.append(appt.provider)
    if appt.specialty:
        bits.append(appt.specialty)
    if appt.date:
        bits.append(appt.date)
    if appt.reason:
        bits.append(appt.reason)
    return " — ".join(bits) if bits else "(appointment details unclear)"


def _build_simulator_user_message(extraction: ExtractionOutput) -> str:
    """
    Build the user message for the patient simulator.

    Serializes extraction into a readable summary: primary/secondary
    diagnosis, medications, follow-ups, red flags, activity/diet.
    Omits procedures_performed.
    """
    lines: list[str] = []
    lines.append(f"Primary diagnosis: {extraction.primary_diagnosis}")
    sec = extraction.secondary_diagnoses or []
    lines.append(
        "Secondary diagnoses: " + (", ".join(sec) if sec else "none")
    )
    meds = extraction.medications or []
    if meds:
        lines.append("")
        lines.append("Medications:")
        for m in meds:
            lines.append(f"  - {_med_bullet(m)}")
    appts = extraction.follow_up_appointments or []
    if appts:
        lines.append("")
        lines.append("Follow-up appointments:")
        for a in appts:
            lines.append(f"  - {_appt_bullet(a)}")
    _append_bullets(
        lines, "Red-flag symptoms:", list(extraction.red_flag_symptoms or [])
    )
    _append_bullets(
        lines,
        "Activity restrictions:",
        list(extraction.activity_restrictions or []),
    )
    _append_bullets(
        lines,
        "Dietary restrictions:",
        list(extraction.dietary_restrictions or []),
    )
    return "\n".join(lines)


def _map_severity(raw: str) -> Literal["critical", "moderate", "minor"]:
    """Map SEVERITY line to enum; default moderate."""
    s = raw.strip().lower()
    if s in ("critical", "moderate", "minor"):
        return s  # type: ignore[return-value]
    return "moderate"


def _parse_q_block(chunk: str) -> MissedConcept | None:
    """Parse one Q:/ANSWERED/GAP/SEVERITY block into MissedConcept."""
    chunk = chunk.strip()
    if not chunk:
        return None
    lines = chunk.splitlines()
    question = lines[0].strip()
    answered_val: str | None = None
    gap = ""
    severity_raw = "moderate"
    for line in lines[1:]:
        u = line.upper().strip()
        if u.startswith("ANSWERED:"):
            answered_val = line.split(":", 1)[1].strip().upper()
        elif line.upper().startswith("GAP:"):
            gap = line.split(":", 1)[1].strip()
        elif line.upper().startswith("SEVERITY:"):
            severity_raw = line.split(":", 1)[1].strip()
    if answered_val is None or not question:
        return None
    answered_by_doc = answered_val == "YES"
    if not gap:
        gap = "N/A" if answered_by_doc else ""
    return MissedConcept(
        question=question,
        answered_by_doc=answered_by_doc,
        gap_summary=gap,
        severity=_map_severity(severity_raw),
    )


def _split_questions_and_tail(raw: str) -> tuple[str, str]:
    """Split Q blocks from OVERALL_GAP_SCORE / SUMMARY tail."""
    m = re.search(r"(?m)^OVERALL_GAP_SCORE:\s*", raw)
    if not m:
        return raw.strip(), ""
    return raw[: m.start()].strip(), raw[m.start() :].strip()


def _parse_tail_scores(tail: str) -> tuple[int, str]:
    """Parse OVERALL_GAP_SCORE and SUMMARY from tail section."""
    score = 5
    mo = re.search(r"(?m)^OVERALL_GAP_SCORE:\s*(\d+)", tail)
    if mo:
        try:
            score = max(0, min(10, int(mo.group(1))))
        except ValueError:
            pass
    summary = ""
    ms = re.search(r"(?m)^SUMMARY:\s*(.*)", tail, re.DOTALL)
    if ms:
        summary = (ms.group(1) or "").strip()
    return score, summary


def _text_for_fk(concepts: list[MissedConcept], simulator_summary: str) -> str:
    """Concatenate gap texts and summary for Flesch-Kincaid."""
    gaps = [
        c.gap_summary
        for c in concepts
        if c.gap_summary and c.gap_summary.strip().upper() != "N/A"
    ]
    joined = " ".join(gaps + [simulator_summary]).strip()
    return joined if joined else "."


def _log_fk_row(document_id: str, fk_grade: float, passes: bool) -> None:
    """Append Agent 6 FK row to evaluation/fk_log.csv."""
    _FK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not _FK_LOG_PATH.exists()
    try:
        with open(_FK_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "document_id",
                    "agent",
                    "fk_grade",
                    "passes",
                    "threshold",
                ],
            )
            if write_header:
                w.writeheader()
            w.writerow({
                "document_id": document_id,
                "agent": "agent6_patient_simulator",
                "fk_grade": fk_grade,
                "passes": passes,
                "threshold": _FK_THRESHOLD,
            })
    except OSError as exc:
        logger.warning("Agent 6 FK log write failed for '%s': %s", document_id, exc)


def _parse_simulator_response(
    raw: str, extraction: ExtractionOutput, document_id: str
) -> PatientSimulatorOutput:
    """
    Parse LLM Q/ANSWERED/GAP/SEVERITY blocks into PatientSimulatorOutput.

    Computes fk_grade via textstat on gap summaries + simulator summary.
    Appends fk_log row. Raises ValueError if fewer than 3 questions parsed.
    """
    _ = extraction  # Reserved for future validation against extraction scope.
    q_body, tail = _split_questions_and_tail(raw)
    parts = re.split(r"(?m)^Q:\s*", q_body)
    chunks = [p.strip() for p in parts if p.strip()]
    concepts: list[MissedConcept] = []
    for ch in chunks:
        mc = _parse_q_block(ch)
        if mc is not None:
            concepts.append(mc)
    if len(concepts) < 3:
        raise ValueError(
            f"Agent 6 parse: expected at least 3 questions, got {len(concepts)}"
        )
    overall_gap, summary = _parse_tail_scores(tail)
    fk_sample = _text_for_fk(concepts, summary)
    raw_fk = textstat.flesch_kincaid_grade(fk_sample)
    fk_grade = round(float(raw_fk), 2)
    passes = raw_fk <= _FK_THRESHOLD
    out = PatientSimulatorOutput(
        missed_concepts=concepts,
        overall_gap_score=overall_gap,
        simulator_summary=summary,
        fk_grade=fk_grade,
        passes=passes,
    )
    _log_fk_row(document_id, fk_grade, passes)
    return out


def _call_llm(
    client: OpenAI,
    model_name: str,
    system_prompt: str,
    user_message: str,
    document_id: str,
) -> str:
    """Invoke shared chat helper for Agent 6."""
    provider = os.environ.get("LLM_PROVIDER", "openrouter").lower()
    return call_chat_with_fallback(
        client=client,
        model_name=model_name,
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=_MAX_TOKENS,
        provider=provider,
        agent_name="agent6_patient_simulator",
        document_id=document_id,
    )


def _fetch_raw_simulator_output(
    extraction: ExtractionOutput,
    document_id: str,
) -> str:
    """Call the LLM; return stripped text or raise."""
    system_prompt = _load_system_prompt()
    user_message = _build_simulator_user_message(extraction)
    client, model_name = get_llm_client()
    try:
        return _call_llm(
            client, model_name, system_prompt, user_message, document_id
        )
    except APIError as exc:
        logger.error(
            "agent6_patient_simulator API error for '%s': %s", document_id, exc
        )
        raise ValueError(f"Agent 6 LLM failure: {exc}") from exc
    except Exception as exc:
        logger.error(
            "agent6_patient_simulator call failed for '%s': %s", document_id, exc
        )
        raise


def run_patient_simulator_agent(
    extraction: ExtractionOutput,
    document_id: str,
) -> PatientSimulatorOutput:
    """
    Run the AI patient simulator on an extracted discharge document.

    Args:
        extraction: Structured extraction output from Agent 1.
        document_id: Source document path/ID for logging.

    Returns:
        PatientSimulatorOutput with missed concepts and gap score.

    Raises:
        ValueError: If the LLM returns empty content or parsing fails.
    """
    raw = _fetch_raw_simulator_output(extraction, document_id)
    if not raw:
        raise ValueError(
            f"agent6_patient_simulator: empty completion for '{document_id}'"
        )
    try:
        out = _parse_simulator_response(raw, extraction, document_id)
    except ValueError:
        logger.error("agent6_patient_simulator parse failed for '%s'", document_id)
        raise
    missed = sum(1 for c in out.missed_concepts if not c.answered_by_doc)
    logger.info(
        "agent6_patient_simulator complete '%s' gap_score=%d missed=%d fk=%.2f",
        document_id,
        out.overall_gap_score,
        missed,
        out.fk_grade,
    )
    return out
