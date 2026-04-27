"""
agents/patient_simulator_agent.py

Agent 6 — AI Patient Simulator
Owner: Likitha

Simulates a patient reading the structured extraction and asks plain-language
questions about gaps between what the document says and what a lay reader might
still misunderstand. Output is parsed into MissedConcept rows, an overall
gap score, a short summary, and a Flesch-Kincaid grade on the gap text (for
eval / logging only — not shown to patients in the main Streamlit flow).

Every run appends one FK row to dischargeiq/evaluation/fk_log.csv under
agent key agent6_patient_simulator.

LLM provider and model are resolved from LLM_PROVIDER / LLM_MODEL in .env via
dischargeiq.utils.llm_client.get_llm_client(), same as Agent 2. The completion
path uses call_chat_with_fallback() for OpenRouter resilience.

Data contract:
    Input:  dischargeiq.models.extraction.ExtractionOutput (from Agent 1)
    Output: dischargeiq.models.pipeline.PatientSimulatorOutput
                missed_concepts     (list[MissedConcept])
                overall_gap_score   (int, 0–10)
                simulator_summary   (str)
                fk_grade            (float)
                passes              (bool) — vs internal _FK_THRESHOLD

Dependencies:
    - openai             (OpenAI-compatible client, used for all providers)
    - textstat           (Flesch-Kincaid on gap summaries + summary)
    - dischargeiq.utils.llm_client (get_llm_client, call_chat_with_fallback)
    - dischargeiq.models.extraction.ExtractionOutput
    - dischargeiq.models.pipeline (MissedConcept, PatientSimulatorOutput)
    - dischargeiq/prompts/agent6_system_prompt.txt

BLOCKED BY: Agent 1 — requires validated ExtractionOutput. Typically
invoked from evaluation or orchestration paths after extraction succeeds.
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

# ── Configuration ──────────────────────────────────────────────────────────────

_MAX_TOKENS = 1200
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_FK_LOG_PATH = Path(__file__).parent.parent / "evaluation" / "fk_log.csv"
_FK_THRESHOLD = 8.0

_FALLBACK_OUTPUT = PatientSimulatorOutput(
    missed_concepts=[],
    overall_gap_score=0,
    simulator_summary="",
    fk_grade=0.0,
    passes=False,
)


# ── Internal helpers ───────────────────────────────────────────────────────────


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


def _normalize_agent6_raw(raw: str) -> str:
    """
    Strip markdown and noisy formatting before parsing Agent 6 output.

    Removes bold/italic markers, heading lines, horizontal rules, blockquotes,
    and leading bullet characters so Q:/SUMMARY patterns match reliably across
    LLM format drift. Also strips the calibration table the prompt includes as
    a reference guide if the LLM accidentally echoes it back.
    """
    text = raw
    # Strip bold/italic markers iteratively until stable.
    # Use word-boundary guards on italic underscores so SCREAMING_SNAKE_CASE
    # labels like OVERALL_GAP_SCORE are not destroyed.
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\*+([^*]+?)\*+", r"\1", text)
        text = re.sub(r"(?<!\w)_([^_]+?)_(?!\w)", r"\1", text)
    # Remove the calibration table if echoed back (reference-only section).
    text = re.sub(
        r"(?is)GAP SCORE CALIBRATION.*?(?=\nQ\s*[:.]|\nOVERALL_GAP_SCORE|\Z)",
        "",
        text,
    )
    lines_out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        if re.match(r"^-{3,}$", s):
            continue
        if s.startswith(">"):
            continue
        # Strip leading bullet characters but keep the rest of the line.
        if re.match(r"^[\*\-]\s", s):
            lines_out.append(s[2:].rstrip())
            continue
        lines_out.append(line.rstrip())
    text = "\n".join(lines_out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_q_block(chunk: str) -> MissedConcept | None:
    """
    Parse one question block into a MissedConcept.

    Handles common LLM format drift:
    - ANSWERED line missing → infer from GAP content (N/A → answered, text → not)
    - Multi-line GAP values → join continuation lines
    - Inline ANSWERED on the Q: line (e.g. "Q: ... ANSWERED: NO") → extracted
    """
    chunk = chunk.strip()
    if not chunk:
        return None
    lines = chunk.splitlines()
    question = lines[0].strip()
    question = re.sub(r"^Q\s*[:\.]\s*", "", question, flags=re.I).strip()
    # Handle inline ANSWERED on the Q line ("Q: ... ANSWERED: NO").
    inline = re.search(r"\bANSWERED\s*:\s*(YES|NO)\b", question, re.I)
    inline_answered: str | None = None
    if inline:
        inline_answered = inline.group(1).upper()
        question = question[: inline.start()].strip()
    if not question:
        return None

    answered_val: str | None = inline_answered
    gap_parts: list[str] = []
    severity_raw = "moderate"

    i = 1
    while i < len(lines):
        line = lines[i]
        if re.match(r"^\s*answered\s*:", line, re.I):
            answered_val = line.split(":", 1)[1].strip().upper()
        elif re.match(r"^\s*gap\s*:", line, re.I):
            gap_parts.append(line.split(":", 1)[1].strip())
            # Collect continuation lines (indented or not starting with a label).
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if re.match(r"^\s*(answered|gap|severity|q)\s*:", lines[j], re.I):
                    break
                if nxt:
                    gap_parts.append(nxt)
                j += 1
            i = j
            continue
        elif re.match(r"^\s*severity\s*:", line, re.I):
            severity_raw = line.split(":", 1)[1].strip()
        i += 1

    gap = " ".join(gap_parts).strip()
    has_gap = bool(gap)
    has_sev = severity_raw != "moderate"
    has_ans = answered_val is not None

    # Reject blocks with no structured labels at all.
    if not has_ans and not has_gap and not has_sev:
        return None

    if answered_val is None:
        # Infer from gap text: "N/A" or empty → answered; real text → not answered.
        answered_by_doc = not has_gap or gap.strip().upper() == "N/A"
    else:
        tok = answered_val.split()
        answered_by_doc = bool(tok and tok[0] == "YES")

    if not gap:
        gap = "N/A" if answered_by_doc else "No additional detail provided."

    return MissedConcept(
        question=question,
        answered_by_doc=answered_by_doc,
        gap_summary=gap,
        severity=_map_severity(severity_raw),
    )


def _concepts_from_q_body(q_body: str) -> list[MissedConcept]:
    """
    Split question body into blocks and parse each into a MissedConcept.

    Strategy (in priority order):
    1. Split on explicit Q: / Q. markers — the canonical format.
    2. Split on "N. Q:" patterns (numbered + Q: on same line).
    3. Fall back to bare numbered list (1. / 1) prefixes).
    Return whichever strategy produces the most parsed concepts.
    """
    _MIN = 2  # accept ≥2 parsed concepts (down from 3 — ER docs can be short)

    def _parse_chunks(chunks: list[str]) -> list[MissedConcept]:
        return [c for c in (_parse_q_block(ch) for ch in chunks) if c]

    # Strategy 1 — explicit Q: markers.
    parts_q = re.split(r"(?m)^\s*Q\s*[:\.]\s*", q_body)
    concepts_q = _parse_chunks([p.strip() for p in parts_q if p.strip()])
    if len(concepts_q) >= _MIN:
        return concepts_q

    # Strategy 2 — "1. Q:" combined prefix.
    parts_nq = re.split(r"(?m)^\s*\d+[\.\)]\s*Q\s*[:\.]\s*", q_body)
    concepts_nq = _parse_chunks([p.strip() for p in parts_nq if p.strip()])
    if len(concepts_nq) >= _MIN:
        return concepts_nq

    # Strategy 3 — bare numbered list.
    parts_n = re.split(r"(?m)^\s*\d+[\.\)]\s+", q_body)
    concepts_n = _parse_chunks([p.strip() for p in parts_n if p.strip()])
    if len(concepts_n) >= _MIN:
        return concepts_n

    # Return whichever gave us the most, even if under minimum.
    return max([concepts_q, concepts_nq, concepts_n], key=len)


def _parse_overall_gap_and_summary(cleaned: str, document_id: str) -> tuple[int, str]:
    """Extract OVERALL_GAP_SCORE (first int) and SUMMARY; summary may be empty."""
    score = 5
    mo = re.search(r"OVERALL_GAP_SCORE\s*[:\s]+\s*(\d+)", cleaned, re.I)
    if mo:
        try:
            score = max(0, min(10, int(mo.group(1))))
        except ValueError:
            pass
    summary = ""
    ms = re.search(r"(?is)\bSUMMARY\s*:\s*(.*)", cleaned)
    if ms:
        summary = (ms.group(1) or "").strip()
    else:
        logger.warning(
            "agent6 summary missing for '%s' — defaulting to empty", document_id
        )
    return score, summary


def _split_q_body_from_cleaned(cleaned: str) -> str:
    """Text before OVERALL_GAP_SCORE line (case-insensitive), else full."""
    m = re.search(r"(?mi)^\s*OVERALL_GAP_SCORE\s*[:\s]", cleaned)
    if not m:
        return cleaned.strip()
    return cleaned[: m.start()].strip()


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
    Appends fk_log row. Raises ValueError if fewer than 2 questions parsed.
    """
    _ = extraction  # Reserved for future validation against extraction scope.
    cleaned = _normalize_agent6_raw(raw)
    q_body = _split_q_body_from_cleaned(cleaned)
    concepts = _concepts_from_q_body(q_body)
    if len(concepts) < 2:
        raise ValueError(
            f"Agent 6 parse: fewer than 2 questions parsed, got {len(concepts)}"
        )
    overall_gap, summary = _parse_overall_gap_and_summary(cleaned, document_id)
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
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
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


# ── Public API ─────────────────────────────────────────────────────────────────

def run_patient_simulator_agent(
    extraction: ExtractionOutput,
    document_id: str,
) -> PatientSimulatorOutput:
    """
    Agent 6: Run the AI patient simulator on Agent 1 extraction output.

    Serializes extraction into a readable brief, calls the LLM with
    agent6_system_prompt.txt, and parses Q:/ANSWERED/GAP/SEVERITY blocks plus
    OVERALL_GAP_SCORE and SUMMARY. Computes FK grade on gap text via textstat
    and logs one row to fk_log.csv.

    Provider and model are resolved from LLM_PROVIDER / LLM_MODEL in .env via
    get_llm_client(). Supports openrouter, openai, ollama, and anthropic.

    Data contract:
        Input:  ExtractionOutput from Agent 1.
        Output: PatientSimulatorOutput — missed_concepts, overall_gap_score,
                simulator_summary, fk_grade, passes.

    Args:
        extraction: Validated ExtractionOutput from Agent 1.
        document_id: Source document label for logging and FK log rows.

    Returns:
        PatientSimulatorOutput on success, or a safe zero-value fallback on all
        error paths. Never raises — all failures are logged at WARNING level.
    """
    try:
        raw = _fetch_raw_simulator_output(extraction, document_id)
    except Exception as exc:
        logger.warning(
            "agent6_patient_simulator fetch failed for '%s': %s — returning fallback",
            document_id,
            exc,
        )
        return _FALLBACK_OUTPUT

    if not raw:
        logger.warning(
            "agent6_patient_simulator: empty completion for '%s' — returning fallback",
            document_id,
        )
        return _FALLBACK_OUTPUT

    try:
        out = _parse_simulator_response(raw, extraction, document_id)
    except ValueError as exc:
        salvaged_score = 0
        mo = re.search(r"OVERALL_GAP_SCORE\s*[:\s]+\s*(\d+)", raw, re.I)
        if mo:
            try:
                salvaged_score = max(0, min(10, int(mo.group(1))))
            except ValueError:
                pass
        logger.warning(
            "agent6_patient_simulator parse failed for '%s' (%s) — returning partial fallback",
            document_id,
            exc,
        )
        return PatientSimulatorOutput(
            missed_concepts=[],
            overall_gap_score=salvaged_score,
            simulator_summary="",
            fk_grade=0.0,
            passes=False,
        )

    out = out.model_copy(update={"missed_concepts": list(out.missed_concepts)})
    missed = sum(1 for c in out.missed_concepts if not c.answered_by_doc)
    logger.info(
        "agent6_patient_simulator complete '%s' gap_score=%d missed=%d fk=%.2f",
        document_id,
        out.overall_gap_score,
        missed,
        out.fk_grade,
    )
    return out
