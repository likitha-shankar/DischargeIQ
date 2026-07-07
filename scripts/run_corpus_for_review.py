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

Usage:
  python scripts/run_corpus_for_review.py               # all missing docs
  python scripts/run_corpus_for_review.py --limit 2     # smoke test
  python scripts/run_corpus_for_review.py --force       # regenerate all

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

_CORPUS_DIR = Path("test-data/synthetic")
_OUTPUT_DIR = Path("evaluation/corpus_outputs")


async def generate_outputs(limit: int | None, force: bool) -> tuple[int, int, int]:
    """
    Run the pipeline over corpus PDFs and persist one JSON per document.

    Args:
        limit: Maximum number of documents to process this run (None = all).
        force: When True, regenerate even if an output file already exists.

    Returns:
        (generated, skipped, failed) counts for the run summary.

    Raises:
        FileNotFoundError: If the corpus directory does not exist.
    """
    pdfs = sorted(_CORPUS_DIR.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(
            f"No PDFs in {_CORPUS_DIR} - run scripts/generate_synthetic_corpus.py first."
        )
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated = skipped = failed = 0
    for pdf in pdfs:
        if limit is not None and generated >= limit:
            break
        out_path = _OUTPUT_DIR / f"{pdf.stem}.json"
        if out_path.exists() and not force:
            skipped += 1
            continue

        started = time.monotonic()
        try:
            # Sequential on purpose: parallel corpus runs trip provider rate
            # limits (429) and turn results partial - slower is more complete.
            response = await run_pipeline(str(pdf), session_id=f"corpus-review-{pdf.stem}")
        except Exception as exc:
            logger.error("Pipeline failed for %s: %s", pdf.name, exc)
            failed += 1
            continue

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
    args = parser.parse_args()

    generated, skipped, failed = asyncio.run(generate_outputs(args.limit, args.force))
    logger.info(
        "Done. generated=%d skipped(existing)=%d failed=%d -> %s",
        generated, skipped, failed, _OUTPUT_DIR,
    )
    # Non-zero exit on failures so CI / cron notices, but only after the
    # resumable loop has saved everything that DID succeed.
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
