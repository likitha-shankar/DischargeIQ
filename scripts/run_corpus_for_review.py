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
  python scripts/run_corpus_for_review.py --corpus test-data/synthetic

Requires: LLM provider keys in .env (same as the API). DATABASE_URL optional -
          the pipeline's history write is non-fatal without it.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from dischargeiq.pipeline.orchestrator import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# The real corpus is the default; the synthetic one is restorable with
# `git checkout task-4.4-corpus-lock -- test-data/synthetic` when a run
# against well-formed documents is wanted for comparison.
_DEFAULT_CORPUS_DIR = Path("test-data/mtsamples")
_OUTPUT_DIR = Path("evaluation/corpus_outputs")


async def generate_outputs(
    limit: int | None,
    force: bool,
    corpus_dir: Path = _DEFAULT_CORPUS_DIR,
    delay_seconds: float = 0.0,
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

    Returns:
        (generated, skipped, failed) counts for the run summary.

    Raises:
        FileNotFoundError: If the corpus directory does not exist.
    """
    pdfs = sorted(corpus_dir.glob("*.pdf"))
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
        if out_path.exists() and not force:
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
        warnings_text = " ".join(response.extraction_warnings)
        if "Agent 1 error" in warnings_text:
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

    generated, skipped, failed = asyncio.run(
        generate_outputs(args.limit, args.force, args.corpus, args.delay)
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
