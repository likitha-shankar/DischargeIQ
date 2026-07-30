"""
Builds a real-world (de-identified) discharge-document corpus from MTSamples.

MTSamples publishes de-identified medical transcription samples. Its website
blocks automated clients (HTTP 403), so this script pulls the community CSV
mirror of the same dataset and renders every row whose `medical_specialty` is
"Discharge Summary" into a one-per-file PDF under `test-data/mtsamples/`.

These documents complement (never replace) the locked synthetic corpus in
`test-data/synthetic/` - they are real dictated transcriptions, so they exercise
formatting the synthetic generator never produces (run-on narrative, no
headings, missing follow-up sections).

Dependencies: pandas + reportlab (already in requirements.txt). The PDF writer
is reused from `scripts/generate_synthetic_corpus.py` so both corpora render
identically.

Usage:
    python scripts/build_mtsamples_corpus.py
    python scripts/build_mtsamples_corpus.py --limit 10 --out-dir /tmp/mts
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

# Reuse the synthetic corpus PDF renderer so both corpora look the same to
# pdfplumber (same margins, same font size, same line handling).
from scripts.generate_synthetic_corpus import _text_to_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Community mirror of the MTSamples dump. The upstream site returns 403 to any
# non-browser client, so this is the only scriptable path to the same data.
_SOURCE_CSV = (
    "https://raw.githubusercontent.com/socd06/medical-nlp/master/data/mtsamples.csv"
)

# Rows shorter than this are stubs (a sentence or two) and are not usable as a
# discharge document for pipeline testing.
_MIN_TRANSCRIPTION_CHARS = 400

# The CSV mirror flattened the original documents' line breaks into literal
# commas, so headings run together ("DISCHARGE DIAGNOSES:,1. Syncope.,2. ...").
# A comma directly after a period or colon was a line break in the source; a
# comma after any other character (including a digit, so "1,000" survives) is
# real punctuation and is left alone.
_FLATTENED_LINEBREAK = re.compile(r"(?<=[.:])\s*,\s*")


def _restore_line_breaks(transcription: str) -> str:
    """
    Undoes the CSV mirror's comma-for-newline flattening.

    Args:
        transcription: Raw transcription text from the CSV.

    Returns:
        The same text with structural commas turned back into line breaks and
        runs of blank lines collapsed.
    """
    restored = _FLATTENED_LINEBREAK.sub("\n", transcription)
    # Collapse the blank-line runs the substitution can create around headings.
    return re.sub(r"\n{3,}", "\n\n", restored).strip()


def fetch_discharge_rows(source_csv: str) -> pd.DataFrame:
    """
    Downloads the MTSamples CSV and returns only usable discharge-summary rows.

    Args:
        source_csv: URL or local path of the mtsamples CSV dump.

    Returns:
        DataFrame with columns description / sample_name / transcription,
        filtered to medical_specialty == "Discharge Summary" and to rows whose
        transcription is long enough to be a real document.

    Raises:
        ValueError: If the CSV loads but contains no discharge-summary rows,
                    which means the mirror's schema changed.
    """
    frame = pd.read_csv(source_csv)
    # The CSV pads specialty values with a leading space ("  Discharge Summary").
    is_discharge = frame["medical_specialty"].str.strip() == "Discharge Summary"
    discharge = frame[is_discharge].copy()

    discharge["transcription"] = discharge["transcription"].fillna("")
    long_enough = discharge["transcription"].str.len() >= _MIN_TRANSCRIPTION_CHARS
    usable = discharge[long_enough]

    if usable.empty:
        raise ValueError(
            f"No usable discharge summaries found in {source_csv} - schema may have changed"
        )

    logger.info(
        "Found %d discharge summaries (%d dropped as too short)",
        len(usable),
        len(discharge) - len(usable),
    )
    return usable


def _compose_document(row: pd.Series) -> str:
    """
    Turns one CSV row into the plain text that gets rendered to PDF.

    MTSamples splits the human-readable title from the body, so the title is
    prepended as a header line - without it the PDF opens mid-narrative and
    Agent 1 has no document-level hint at all.

    Args:
        row: One row of the filtered discharge DataFrame.

    Returns:
        Plain-text document body, ready for _text_to_pdf().
    """
    title = str(row.get("sample_name") or "Discharge Summary").strip()
    description = str(row.get("description") or "").strip()

    parts = [f"DISCHARGE SUMMARY - {title}", ""]
    if description and description.lower() != "nan":
        parts.extend([description, ""])
    parts.append(_restore_line_breaks(str(row["transcription"])))
    return "\n".join(parts)


def build_corpus(out_dir: Path, source_csv: str, limit: int | None) -> list[dict]:
    """
    Renders every discharge summary to its own PDF and writes an index file.

    Args:
        out_dir: Directory to write PDFs and corpus_index.json into. Created
                 if missing.
        source_csv: URL or local path of the mtsamples CSV dump.
        limit: Optional cap on how many documents to render (for smoke runs).

    Returns:
        List of index entries, one per PDF written.

    Raises:
        OSError: If out_dir cannot be created or a PDF cannot be written.
    """
    rows = fetch_discharge_rows(source_csv)
    if limit is not None:
        rows = rows.head(limit)

    out_dir.mkdir(parents=True, exist_ok=True)

    index: list[dict] = []
    for position, (_, row) in enumerate(rows.iterrows(), start=1):
        filename = f"mtsamples_{position:03d}.pdf"
        text = _compose_document(row)
        try:
            _text_to_pdf(text, out_dir / filename)
        except Exception as exc:  # reportlab raises a variety of layout errors
            logger.error("Failed to render %s: %s", filename, exc)
            continue

        index.append(
            {
                "file": filename,
                "sample_name": str(row.get("sample_name", "")).strip(),
                "description": str(row.get("description", "")).strip(),
                "char_count": len(text),
            }
        )

    index_path = out_dir / "corpus_index.json"
    index_path.write_text(
        json.dumps(
            {
                "source": source_csv,
                "source_site": "https://www.mtsamples.com/site/pages/browse.asp?type=89-Discharge+Summary",
                "note": "De-identified real transcriptions. NOT the locked synthetic corpus.",
                "document_count": len(index),
                "documents": index,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("Wrote %d PDFs + index to %s", len(index), out_dir)
    return index


def _self_check() -> None:
    """Asserts the line-break restoration on the cases that actually matter."""
    flattened = "DISCHARGE DIAGNOSES:,1. Syncope.,2. Hypertension.,CONDITION: , Stable."
    assert _restore_line_breaks(flattened) == (
        "DISCHARGE DIAGNOSES:\n1. Syncope.\n2. Hypertension.\nCONDITION:\nStable."
    ), _restore_line_breaks(flattened)

    # Commas that are real punctuation must survive untouched.
    prose = "He was given 1,000 mg of drug A, drug B, and drug C."
    assert _restore_line_breaks(prose) == prose, _restore_line_breaks(prose)
    print("self-check OK")


def main() -> None:
    """Parses CLI arguments and builds the MTSamples corpus."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Run the line-break restoration assertions and exit.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).parent.parent / "test-data" / "mtsamples",
        help="Output directory for the rendered PDFs.",
    )
    parser.add_argument(
        "--source-csv",
        default=_SOURCE_CSV,
        help="Override the MTSamples CSV source (URL or local path).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Render only the first N documents (smoke runs).",
    )
    args = parser.parse_args()

    if args.self_check:
        _self_check()
        return

    build_corpus(args.out_dir, args.source_csv, args.limit)


if __name__ == "__main__":
    main()
