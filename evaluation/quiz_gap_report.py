"""
File: evaluation/quiz_gap_report.py
Owner: Likitha Shankar
Description: Quiz-failure analysis for prompt tuning (Sprint 3, Task 3.4) —
  reads quiz_scores + discharge_history from Neon, aggregates miss rates per
  quiz domain (baseline and post-teaching), breaks post-teaching failures
  down by diagnosis, and maps every failing domain to the agent prompt that
  owns it. Output is the evidence a prompt edit must cite: no prompt change
  without a domain failing here first.
Key functions/classes: build_report, main
Edge cases handled:
  - No DATABASE_URL → exits with a clear message, not a traceback.
  - Below MIN_SESSIONS completed loops → report is generated but marked
    LOW CONFIDENCE and no tuning recommendations are emitted.
Dependencies: asyncpg, python-dotenv; reuses query/aggregation helpers from
  ui.quiz_analytics (single source of truth for the miss-rate math).
Called by: manual — `python evaluation/quiz_gap_report.py` from repo root.
  Writes evaluation/quiz_gap_report.md and prints it.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Run from repo root so the shared analytics helpers (the single source of
# truth for baseline/post protocol and miss-rate math) are importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ui.quiz_analytics import (  # noqa: E402
    DOMAIN_LABELS,
    domain_miss_rates,
    fetch_rows,
    quiz_by_session,
)

# Which agent prompt owns each quiz domain — where a persistent failure
# points the tuning work.
_DOMAIN_TO_PROMPT = {
    "diagnosis": "prompts/agent2_system_prompt.txt (What Happened)",
    "medications": "prompts/agent3_system_prompt.txt (Medications)",
    "follow_up": "prompts/agent1_system_prompt.txt (extraction) + appointments tab",
    "activity": "prompts/agent4_system_prompt.txt (Recovery)",
    "red_flags": "prompts/agent5_system_prompt.txt (Warning Signs — safety-critical)",
}

# Below this many completed pre→post loops, per-domain rates are noise:
# with 5 questions/quiz, one patient swings a domain by 100%.
MIN_SESSIONS = 10

# A domain still missed this often AFTER the learning cards is a tuning target.
FLAG_THRESHOLD = 0.20


def _label_to_key(label: str) -> str:
    """Map a display label back to its domain key (inverse of DOMAIN_LABELS)."""
    for key, val in DOMAIN_LABELS.items():
        if val == label:
            return key
    return label


def build_report(history: list[dict], quiz: list[dict]) -> str:
    """
    Build the markdown gap report from raw table rows.

    Args:
        history: discharge_history rows (dicts).
        quiz: quiz_scores rows (dicts, ascending created_at).

    Returns:
        The full markdown report as a string.
    """
    sessions = quiz_by_session(quiz)
    completed = {
        sid: s for sid, s in sessions.items()
        if s["pre"] is not None and s["post"] is not None
    }
    pre_miss = domain_miss_rates(quiz, "pre")
    post_miss = domain_miss_rates(quiz, "post")
    diagnosis_by_sid = {h["session_id"]: h["primary_diagnosis"] or "unknown" for h in history}

    low_confidence = len(completed) < MIN_SESSIONS
    lines = [
        "# Quiz Gap Report — prompt-tuning evidence (Task 3.4)",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Completed pre→post loops: **{len(completed)}** "
        f"(minimum for tuning decisions: {MIN_SESSIONS})",
        "",
    ]
    if low_confidence:
        lines += [
            "> ⚠️ **LOW CONFIDENCE** — below the minimum sample. This run shows the",
            "> pipeline works; do NOT edit prompts from it. Re-run once Sprint 2",
            "> beta testers produce real loops.",
            "",
        ]

    lines += ["## Miss rate per domain", "", "| Domain | Baseline | After teaching | Owning prompt |", "|---|---|---|---|"]
    for label in sorted(set(pre_miss) | set(post_miss)):
        key = _label_to_key(label)
        lines.append(
            f"| {label} | {pre_miss.get(label, 0.0):.0%} | {post_miss.get(label, 0.0):.0%} "
            f"| `{_DOMAIN_TO_PROMPT.get(key, '—')}` |"
        )

    flagged = {
        label: rate for label, rate in post_miss.items() if rate > FLAG_THRESHOLD
    }
    lines += ["", "## Tuning targets", ""]
    if low_confidence:
        lines.append("_None emitted — sample below minimum._")
    elif not flagged:
        lines.append(
            f"_No domain exceeds the {FLAG_THRESHOLD:.0%} post-teaching miss "
            "threshold — prompts are holding._"
        )
    else:
        for label, rate in sorted(flagged.items(), key=lambda kv: kv[1], reverse=True):
            key = _label_to_key(label)
            lines.append(
                f"- **{label}** missed {rate:.0%} after teaching → revise "
                f"`{_DOMAIN_TO_PROMPT.get(key, '?')}`: shorter sentences, one idea "
                "per sentence, restate the domain's key fact in the first line."
            )

    # Post-teaching failures per diagnosis — shows whether a gap is global
    # (prompt problem) or condition-specific (template problem).
    lines += ["", "## Post-teaching failures by diagnosis", ""]
    any_fail = False
    for sid, s in completed.items():
        failed = [
            DOMAIN_LABELS.get(d, d)
            for d, counts in (s["post_domains"] or {}).items()
            if counts.get("correct", 0) < counts.get("total", 0)
        ]
        if failed:
            any_fail = True
            lines.append(f"- `{sid[:8]}` ({diagnosis_by_sid.get(sid, 'unknown')}): {', '.join(failed)}")
    if not any_fail:
        lines.append("_No post-teaching failures recorded._")

    return "\n".join(lines) + "\n"


def _self_check() -> None:
    """Assert the report flags a persistent post-teaching gap (runs offline)."""
    quiz = [
        {"session_id": "s1", "phase": "pre", "percent": 20.0,
         "domain_scores": json.dumps({"medications": {"correct": 0, "total": 1}})},
        {"session_id": "s1", "phase": "post", "percent": 80.0,
         "domain_scores": json.dumps({"medications": {"correct": 0, "total": 1}})},
    ]
    report = build_report([{"session_id": "s1", "primary_diagnosis": "COPD"}], quiz)
    assert "Medications | 100% | 100%" in report, "miss-rate math broke"
    assert "LOW CONFIDENCE" in report, "sample-size guard broke"  # 1 loop < MIN_SESSIONS


def main() -> None:
    """Fetch rows, build the report, write evaluation/quiz_gap_report.md, print it."""
    _self_check()  # free correctness gate before touching the network
    load_dotenv(dotenv_path=".env")
    db_url = os.getenv("DATABASE_URL_RO") or os.getenv("DATABASE_URL")
    if not db_url:
        sys.exit("No DATABASE_URL / DATABASE_URL_RO configured — set one in .env")

    history, quiz = asyncio.run(fetch_rows(db_url))
    report = build_report([dict(r) for r in history], [dict(r) for r in quiz])

    out_path = Path(__file__).resolve().parent / "quiz_gap_report.md"
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Written: {out_path}")


if __name__ == "__main__":
    main()
