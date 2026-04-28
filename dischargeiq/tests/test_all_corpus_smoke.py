"""
File: dischargeiq/tests/test_all_corpus_smoke.py
Owner: Likitha Shankar
Description: Slow, marked integration sweep — runs run_pipeline across fixtures in
  dischargeiq/tests/fixtures, test-data, and stress-test; asserts pipeline_status whitelist,
  FK ceilings for agents 2–5, and Neon discharge_history rows using short-lived DB connections
  per query to avoid idle disconnects on long runs.
Key functions/classes: pytest slow tests, _fresh_query helper (internal)
Edge cases handled:
  - Skipped unless -m slow; uses fresh asyncpg connections for post-run DB verification.
Dependencies: asyncio, asyncpg, pytest, dischargeiq.pipeline.orchestrator, DATABASE_URL when enabled.
Called by: pytest -m slow only.
"""

# stdlib
import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# third-party
import asyncpg
import pytest
from dotenv import load_dotenv

# local
from dischargeiq.pipeline.orchestrator import run_pipeline

# Lower bound for `WHERE created_at >= …` in test_corpus_db_invariants.
# Must be pinned when the pytest session *starts*, not when the last test
# runs: `test_start_ts` was only requested by the final test, so it used to
# default to "now" after all PDFs finished and the COUNT(*) saw 0–1 rows.
_SWEEP_DB_WINDOW_START: datetime | None = None


def _naive_utc_now() -> datetime:
    """UTC 'now' as naive datetime (matches asyncpg TIMESTAMP WITHOUT TIME ZONE)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ──────────────────────────────────────────────────────────────────────────────
# Module-level setup
# ──────────────────────────────────────────────────────────────────────────────

# dischargeiq/tests/test_all_corpus_smoke.py -> parents[2] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Populate DATABASE_URL / provider keys from the repo-root .env before any
# helper runs. load_dotenv is idempotent so importing this module from a
# pytest run that already loaded .env is harmless.
load_dotenv(_REPO_ROOT / ".env")

_WHITELIST = {"complete", "complete_with_warnings", "partial"}
_FK_GATE = 6.0
_AGENT_KEYS = ("agent2", "agent3", "agent4", "agent5")
_PER_FIXTURE_TIMEOUT_SECONDS = 300.0

_FIXTURE_DIRS = (
    _REPO_ROOT / "dischargeiq" / "tests" / "fixtures",
    _REPO_ROOT / "test-data",
    _REPO_ROOT / "test-data" / "stress-test",
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _discover_corpus() -> list[Path]:
    """
    Collect every *.pdf across the three corpus directories.

    The stress-test directory contains two .py generators alongside the
    PDFs; filtering on the .pdf extension via glob excludes them.

    Returns:
        list[Path]: sorted, deterministic list of PDF fixture paths.
                    Empty if none of the directories exist yet.
    """
    pdfs: list[Path] = []
    for directory in _FIXTURE_DIRS:
        if not directory.is_dir():
            continue
        pdfs.extend(directory.glob("*.pdf"))
    return sorted(pdfs)


async def _fresh_query(sql: str, *args: Any) -> list[asyncpg.Record]:
    """
    Run a single SQL query on a freshly-opened asyncpg connection.

    Unlike the /tmp sweep harness, every
    DB read opens a new connection and closes it before returning, so no
    connection is held idle long enough for Neon to drop it server-side.

    Args:
        sql:  The SQL statement. Use $1, $2, ... for parameter binds.
        args: Values bound to $1, $2, ... in order.

    Returns:
        list[asyncpg.Record]: The raw rows returned by conn.fetch().

    Raises:
        asyncpg.PostgresError: On any database-side failure.
        OSError:               On connect-level network failure.
        KeyError:              If DATABASE_URL is not set in the env.
    """
    database_url = os.environ["DATABASE_URL"]
    conn = await asyncpg.connect(database_url)
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


async def _count_rows_since(since: datetime) -> int:
    """
    Count discharge_history rows inserted at or after `since`.

    Args:
        since: Naive UTC datetime (column is TIMESTAMP WITHOUT TIME ZONE).

    Returns:
        int: Row count in the window.

    Raises:
        asyncpg.PostgresError: On DB-side failure.
    """
    rows = await _fresh_query(
        "SELECT COUNT(*) AS n FROM discharge_history WHERE created_at >= $1",
        since,
    )
    return int(rows[0]["n"])


async def _count_invalid_statuses(since: datetime) -> int:
    """
    Count rows in the window whose pipeline_status is outside the whitelist.

    If the pipeline_status CHECK constraint is working, this is always 0;
    this assertion is what detects a future agent introducing a new status
    value without updating the constraint or the orchestrator canon.

    Args:
        since: Naive UTC datetime bounding the test window.

    Returns:
        int: Count of offending rows (expected: 0).

    Raises:
        asyncpg.PostgresError: On DB-side failure.
    """
    rows = await _fresh_query(
        "SELECT COUNT(*) AS n FROM discharge_history "
        "WHERE created_at >= $1 "
        "AND pipeline_status NOT IN "
        "('complete', 'complete_with_warnings', 'partial')",
        since,
    )
    return int(rows[0]["n"])


def _extract_fk_grades(fk_scores: dict) -> dict[str, float | None]:
    """
    Pull the fk_grade for each of agent2..agent5 out of the response dict.

    The pipeline populates fk_scores[agent_key] = {"fk_grade": float,
    "passes": bool} on success and simply omits the key when that agent
    failed, so we default-dig to None rather than KeyError.

    Args:
        fk_scores: The PipelineResponse.fk_scores dict.

    Returns:
        dict[str, float | None]: Mapping of agent key -> grade or None.
    """
    return {
        key: (fk_scores.get(key) or {}).get("fk_grade")
        for key in _AGENT_KEYS
    }


def _format_pass_line(
    pdf: Path, status: str, grades: dict, elapsed: float
) -> str:
    """
    Build the one-line stdout summary that `pytest -s` emits per fixture.

    Args:
        pdf:     Fixture path.
        status:  pipeline_status returned by the run.
        grades:  Output of _extract_fk_grades().
        elapsed: Wall-clock seconds for the run.

    Returns:
        str: e.g. "[PASS]  fixture_09_epic_chf.pdf  status=complete
             FK: a2=5.1 a3=4.8 a4=4.9 a5=5.3  elapsed=32.1s"
    """
    fk_chunks = []
    for key in _AGENT_KEYS:
        grade = grades.get(key)
        fk_chunks.append(
            f"{key.replace('agent', 'a')}={'?' if grade is None else f'{grade:.1f}'}"
        )
    fk_str = " ".join(fk_chunks)
    return (
        f"[PASS]  {pdf.name}  status={status}  "
        f"FK: {fk_str}  elapsed={elapsed:.1f}s"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Session-scoped fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def _pin_db_query_window_for_corpus_sweep() -> Iterator[None]:
    """
    Run once at session start (before any parametrized PDF case).

    Binds the DB aggregation window so rows written during the ~20+ minute
    sweep are all `created_at >= test_start_ts`.
    """
    global _SWEEP_DB_WINDOW_START
    _SWEEP_DB_WINDOW_START = _naive_utc_now() - timedelta(seconds=2)
    yield


@pytest.fixture(scope="session")
def test_start_ts() -> datetime:
    """
    Naive UTC lower bound for discharge_history rows belonging to this sweep.

    Returns:
        datetime: Naive UTC datetime for `WHERE created_at >= $1`.
    """
    assert _SWEEP_DB_WINDOW_START is not None
    return _SWEEP_DB_WINDOW_START


@pytest.fixture(scope="session")
def corpus_size() -> int:
    """Number of fixtures the parametrized test will process."""
    return len(_discover_corpus())


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.slow
@pytest.mark.parametrize(
    "pdf_path", _discover_corpus(), ids=lambda p: p.name
)
def test_corpus_fixture_passes(pdf_path: Path) -> None:
    """
    Run the pipeline on one fixture; assert whitelist + FK-gate invariants.

    Belt-and-suspenders: `run_pipeline` already applies its own 300-second
    asyncio.wait_for internally. The outer wait_for here
    ensures the test harness itself can never hang.

    Args:
        pdf_path: The fixture PDF for this parametrized case.

    Raises:
        AssertionError:       On any invariant violation.
        asyncio.TimeoutError: If the pipeline exceeds the per-fixture budget.
        Exception:            Any other uncaught pipeline failure, re-raised
                              after the failure line is printed.
    """
    start = time.perf_counter()
    try:
        response = asyncio.run(
            asyncio.wait_for(
                run_pipeline(str(pdf_path)),
                timeout=_PER_FIXTURE_TIMEOUT_SECONDS,
            )
        )
    except Exception as exc:
        elapsed = time.perf_counter() - start
        print(
            f"[FAIL]  {pdf_path.name}  "
            f"exception after {elapsed:.1f}s: {type(exc).__name__}: {exc}"
        )
        raise
    elapsed = time.perf_counter() - start

    status = response.pipeline_status
    assert status in _WHITELIST, (
        f"{pdf_path.name}: status={status!r} not in {_WHITELIST}"
    )

    grades = _extract_fk_grades(response.fk_scores or {})

    if status != "partial":
        for key in _AGENT_KEYS:
            assert grades[key] is not None, (
                f"{pdf_path.name}: missing fk_grade for {key} "
                f"on non-partial run (status={status})"
            )

    for key, grade in grades.items():
        if grade is not None:
            assert grade <= _FK_GATE, (
                f"{pdf_path.name}: {key} FK grade {grade} "
                f"exceeds gate {_FK_GATE}"
            )

    print(_format_pass_line(pdf_path, status, grades, elapsed))


@pytest.mark.slow
def test_corpus_db_invariants(
    corpus_size: int, test_start_ts: datetime
) -> None:
    """
    Post-parametrize aggregation check against Neon.

    Declared after `test_corpus_fixture_passes` in the module so pytest
    collects it second and runs it after all 35 parametrized cases have
    written their rows. Opens a fresh asyncpg connection per query via
    _fresh_query — no long-lived connection is held anywhere in this test.

    Args:
        corpus_size:   Fixture count, from the session-scoped fixture.
        test_start_ts: Sweep-start timestamp, from the session-scoped fixture.

    Raises:
        AssertionError: If row count mismatches corpus size, or if any row
                        in the window fell outside the CHECK whitelist.
    """
    try:
        actual_rows = asyncio.run(_count_rows_since(test_start_ts))
        invalid = asyncio.run(_count_invalid_statuses(test_start_ts))
    except (asyncpg.PostgresError, OSError, KeyError) as exc:
        pytest.fail(f"DB aggregation query failed: {type(exc).__name__}: {exc}")

    assert actual_rows == corpus_size, (
        f"Expected {corpus_size} rows written since {test_start_ts}, "
        f"got {actual_rows}"
    )
    assert invalid == 0, (
        f"{invalid} row(s) have a pipeline_status outside the whitelist"
    )
    print(f"[AGG]  rows={actual_rows}  invalid={invalid}")
