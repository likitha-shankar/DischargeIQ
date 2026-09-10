"""
scripts/run_corpus_for_review.py

Sprint 5, Task 5.1 - Generate pipeline outputs for the clinician review portal.
Owner: Likitha Shankar

Runs the full agent pipeline over every PDF in the locked synthetic corpus and
writes one JSON file per document to evaluation/corpus_outputs/. The clinician
review portal (ui/clinician_review.py) reads these files so reviewers score a
FROZEN set of outputs - regenerating mid-review would invalidate scores.

Repo rule respected: agent free-text is stored on disk in the repo workspace,
never in the database. Neon only ever receives the structured rubric scores.

Resumable by design: documents with an existing output JSON are skipped, so a
rate-limit crash or Ctrl-C loses nothing. Use --force to regenerate everything
(only before review starts - never after clinicians have begun scoring).

Corpus (decision, 30 Jul 2026): the primary corpus is the 106 real
de-identified MTSamples summaries, which replaced the 50 generated synthetic
documents. This script pointed at test-data/synthetic long after that
directory stopped existing, which is why the run was never completed - it
raised FileNotFoundError before touching a single document. The default is now
the real corpus, with --corpus for anything else.

Usage:
  python scripts/run_corpus_for_review.py               # all missing docs
  python scripts/run_corpus_for_review.py --limit 20    # a review sample
  python scripts/run_corpus_for_review.py --force       # regenerate all
  python scripts/run_corpus_for_review.py --stale       # only out-of-date ones
  python scripts/run_corpus_for_review.py --count-stale # 'todo total', no API
  python scripts/run_corpus_for_review.py --corpus test-data/synthetic

Requires: LLM provider keys in .env (same as the API). DATABASE_URL optional -
          the pipeline's history write is non-fatal without it.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from dischargeiq.pipeline.orchestrator import run_pipeline
from dischargeiq.utils.strata import stratum_of_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# The real corpus is the default; the synthetic one is restorable with
# `git checkout task-4.4-corpus-lock -- test-data/synthetic` when a run
# against well-formed documents is wanted for comparison.
_DEFAULT_CORPUS_DIR = Path("test-data/mtsamples")
_OUTPUT_DIR = Path("evaluation/corpus_outputs")
_PROMPT_DIR = Path(__file__).resolve().parents[1] / "dischargeiq" / "prompts"


def prompt_versions() -> dict[str, str]:
    """
    A short content hash of every agent prompt, for output provenance.

    Prompts change more often than models on this project and change output
    just as much, so "which model" alone cannot tell two runs apart. A hash is
    used rather than a timestamp because it survives a file being touched,
    reformatted or checked out, and it changes if and only if the text does.

    Returns:
        Prompt filename stem -> first 8 hex characters of its SHA-256. An
        unreadable prompt maps to "unknown" rather than raising: provenance is
        metadata, and losing it must never fail a corpus run.
    """
    versions: dict[str, str] = {}
    for path in sorted(_PROMPT_DIR.glob("*.txt")):
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
        except OSError:
            digest = "unknown"
        versions[path.stem] = digest
    return versions


def is_stale(out_path: Path) -> bool:
    """
    Whether an output was produced by prompts that have since changed.

    An output that exists is not necessarily current. On 25 Aug 2026 three
    agent prompts changed and 54 outputs kept sitting on disk looking complete,
    which would have let the catch-up job declare the corpus finished while
    most of it described the old system.

    Args:
        out_path: Path to one output JSON.

    Returns:
        True when the file is unreadable, carries no prompt stamp, or its stamp
        differs from the prompts on disk. Unreadable and unstamped both count as
        stale on purpose: the safe assumption about an output we cannot vouch
        for is that it needs regenerating.
    """
    try:
        meta = json.loads(out_path.read_text()).get("_review_meta") or {}
    except (OSError, ValueError):
        return True
    recorded = meta.get("prompt_versions")
    if not recorded:
        return True
    return recorded != prompt_versions()


def count_stale(corpus_dir: Path = _DEFAULT_CORPUS_DIR) -> tuple[int, int]:
    """
    How much of the corpus still needs regenerating.

    Args:
        corpus_dir: Directory of source PDFs.

    Returns:
        (missing_or_stale, total_documents).
    """
    pdfs = sorted(corpus_dir.glob("*.pdf"))
    todo = sum(
        1 for pdf in pdfs
        if not (_OUTPUT_DIR / f"{pdf.stem}.json").exists()
        or is_stale(_OUTPUT_DIR / f"{pdf.stem}.json")
    )
    return todo, len(pdfs)


async def generate_outputs(
    limit: int | None,
    force: bool,
    corpus_dir: Path = _DEFAULT_CORPUS_DIR,
    delay_seconds: float = 0.0,
    stale_only: bool = False,
    only: set[str] | None = None,
) -> tuple[int, int, int]:
    """
    Run the pipeline over corpus PDFs and persist one JSON per document.

    Args:
        limit: Maximum number of documents to process this run (None = all).
        force: When True, regenerate even if an output file already exists.
        corpus_dir: Directory of source PDFs. Defaults to the real corpus.
        delay_seconds: Pause between documents. Vertex enforces a
            per-minute quota that six sequential agent calls exhaust
            quickly, so pacing turns a run that dies at document three
            into one that finishes.
        stale_only: When True, also regenerate outputs whose prompt stamp no
            longer matches the prompts on disk. Unlike force, current outputs
            are still skipped, so repeated runs converge instead of looping.
        only: Document stems to process, or None for the whole corpus. Added
            because the staleness check compares PROMPT and MODEL stamps, so a
            change to post-generation code - the threshold guard, for instance
            - leaves every document looking current. The alternative was
            regenerating all 106 to exercise two, which burns quota and churns
            every golden baseline at once, hiding real drift in the noise.

    Returns:
        (generated, skipped, failed) counts for the run summary.

    Raises:
        FileNotFoundError: If the corpus directory does not exist.
    """
    pdfs = sorted(corpus_dir.glob("*.pdf"))
    if only:
        wanted = sorted(p for p in pdfs if p.stem in only)
        missing = only - {p.stem for p in wanted}
        if missing:
            # Loudly, not silently: a typo in a document id would otherwise
            # produce a short clean run that looks like a pass.
            raise FileNotFoundError(
                f"--docs named {len(missing)} document(s) not in {corpus_dir}: "
                f"{sorted(missing)}")
        pdfs = wanted
    if not pdfs:
        raise FileNotFoundError(
            f"No PDFs in {corpus_dir}. The real corpus is gitignored and is "
            f"rebuilt with scripts/build_mtsamples_corpus.py; the synthetic "
            f"one is restored with "
            f"`git checkout task-4.4-corpus-lock -- test-data/synthetic`."
        )
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated = skipped = failed = 0
    quota_strikes = 0
    for pdf in pdfs:
        if limit is not None and generated >= limit:
            break
        out_path = _OUTPUT_DIR / f"{pdf.stem}.json"
        if out_path.exists() and not force and not (stale_only and is_stale(out_path)):
            skipped += 1
            continue

        # Pace before the work, not after, so the delay also separates a
        # retried document from the one that just tripped the quota.
        if delay_seconds and (generated or failed):
            await asyncio.sleep(delay_seconds)

        started = time.monotonic()
        try:
            # Sequential on purpose: parallel corpus runs trip provider rate
            # limits (429) and turn results partial - slower is more complete.
            response = await run_pipeline(str(pdf), session_id=f"corpus-review-{pdf.stem}")
        except Exception as exc:
            logger.error("Pipeline failed for %s: %s", pdf.name, exc)
            failed += 1
            continue

        # Quota circuit breaker (lesson from the Jul 7 run: a provider whose
        # daily quota is exhausted fails EVERY document in ~2s - continuing
        # burns the remaining quota on retries and fills the review set with
        # unusable JSON). Two consecutive quota/credit failures -> abort;
        # the run is resumable, so nothing already saved is lost.
        # Any Agent 1 failure means the document produced no extraction, so the
        # output is unusable for review whatever the cause. This used to test
        # for 429/credit only, and a misconfigured model name (HTTP 400 on
        # every call) sailed straight past it: the run reported
        # "generated=20 failed=0" while writing twenty partial files with
        # "Extraction failed" as the diagnosis. Judge the outcome, not the
        # error code.
        # A run is unusable for review if ANY narrative section came back
        # empty. Agent 1 can succeed while agents 2-5 die one at a time on a
        # rate limit, and the result is a document a clinician is asked to
        # score with a blank section in it - which scores the outage, not the
        # system. Eight such files reached the committed review set on
        # 15 Aug before this check existed.
        empty_sections = [
            name for name, value in (
                ("diagnosis", response.diagnosis_explanation),
                ("medication", response.medication_rationale),
                ("recovery", response.recovery_trajectory),
                ("escalation", response.escalation_guide),
            ) if not str(value or "").strip()
        ]
        warnings_text = " ".join(response.extraction_warnings)
        if "Agent 1 error" in warnings_text or empty_sections:
            if empty_sections and "Agent 1 error" not in warnings_text:
                warnings_text = (
                    f"empty after agent failure: {', '.join(empty_sections)}"
                )
            quota_strikes += 1
            failed += 1
            logger.error(
                "%s: extraction failed (%d/2) - output NOT saved: %s",
                pdf.name, quota_strikes, warnings_text[:200],
            )
            if quota_strikes >= 2:
                logger.error(
                    "Two consecutive extraction failures - aborting rather "
                    "than filling the review set with unusable JSON. Check "
                    "the error above (quota, credit, or a bad LLM_MODEL for "
                    "this provider), then re-run; existing outputs are kept."
                )
                break
            continue
        quota_strikes = 0

        payload = response.model_dump()
        payload["_review_meta"] = {
            "doc_name": pdf.stem,
            "source_pdf": str(pdf),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "elapsed_seconds": round(time.monotonic() - started, 1),
            # Which model produced this output. Without it the accuracy report
            # cannot say what it measured, and a provider-side change to a
            # floating alias like "gemini-2.5-flash-lite" silently invalidates
            # every number in it while the file still looks current. Raised as
            # item 3.7 of the Liebovitz review.
            "llm_provider": os.environ.get("LLM_PROVIDER", "gemini"),
            "llm_model": os.environ.get("LLM_MODEL", "") or "<provider default>",
            # Which PROMPTS produced it. The model stamp above is not enough:
            # on 25 Aug 2026 three agent prompts changed within an hour and
            # nothing in an output distinguished before from after, so a
            # baseline was auto-saved mixing both and labelled as though the
            # whole corpus had been regenerated. Prompts change far more often
            # than models here, and they change output just as much.
            "prompt_versions": prompt_versions(),
            # Which SOURCE FORMAT this document is. Accuracy reported as one
            # blended number hides whether extraction is failing on faxes
            # while looking fine overall (Liebovitz review item 3.3).
            "stratum": stratum_of_file(pdf).value,
        }
        out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        generated += 1
        logger.info(
            "%s -> %s (%s, %.0fs)",
            pdf.name, out_path.name, response.pipeline_status,
            time.monotonic() - started,
        )
    return generated, skipped, failed


def main() -> None:
    """Parse args and run the corpus generation loop."""
    parser = argparse.ArgumentParser(description="Generate corpus outputs for clinician review")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N documents")
    parser.add_argument("--force", action="store_true", help="Regenerate existing outputs")
    parser.add_argument(
        "--docs", nargs="*", metavar="STEM",
        help="Regenerate only these document stems (implies --force for them)")
    parser.add_argument(
        "--stale", action="store_true",
        help="Regenerate only outputs whose prompt stamp differs from the "
             "prompts on disk (and anything missing). Unlike --force this does "
             "not redo work that is already current, so it is safe to run "
             "repeatedly until count-stale reports zero.",
    )
    parser.add_argument(
        "--count-stale", action="store_true",
        help="Print 'todo total' and exit. Makes no API calls.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds to wait between documents (use ~30 on Vertex quota)",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=_DEFAULT_CORPUS_DIR,
        help=f"Directory of source PDFs (default: {_DEFAULT_CORPUS_DIR})",
    )
    args = parser.parse_args()

    # Cheap query mode: the catch-up loop calls this between batches to decide
    # whether to keep going, so it must never touch the API.
    if args.count_stale:
        todo, total = count_stale(args.corpus)
        print(f"{todo} {total}")
        return

    generated, skipped, failed = asyncio.run(
        generate_outputs(args.limit, args.force or bool(args.docs),
                         args.corpus, args.delay,
                         stale_only=args.stale,
                         only=set(args.docs) if args.docs else None)
    )
    logger.info(
        "Done. generated=%d skipped(existing)=%d failed=%d -> %s",
        generated, skipped, failed, _OUTPUT_DIR,
    )
    # Non-zero exit on failures so CI / cron notices, but only after the
    # resumable loop has saved everything that DID succeed.
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
