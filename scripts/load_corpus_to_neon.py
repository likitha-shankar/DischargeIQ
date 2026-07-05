"""
scripts/load_corpus_to_neon.py

Sprint 1, Task 1.6 - Load the synthetic corpus metadata into Neon.
Owner: Likitha Shankar

Reads test-data/synthetic/corpus_index.json (written by
generate_synthetic_corpus.py) and upserts one row per document into the
synthetic_corpus table, creating the table if it does not exist. This
populates the testing matrix that Month 3's clinician review and the
comprehension-lift analysis query against.

Only structured metadata is stored - never raw document text (repo rule:
no full PDF text in the database).

Usage:
  cd /path/to/DischargeIQ
  python scripts/load_corpus_to_neon.py [--index test-data/synthetic/corpus_index.json]

Requires: DATABASE_URL in .env (Neon PostgreSQL connection string).
          Exits with a clear message (code 1) when unset - never crashes.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# One row per corpus document. doc_name is the natural key so re-running the
# loader after regenerating a document updates in place instead of duplicating.
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_corpus (
    id SERIAL PRIMARY KEY,
    doc_name VARCHAR(64) NOT NULL UNIQUE,
    category VARCHAR(32) NOT NULL,
    patient_age INT,
    patient_sex VARCHAR(10),
    severity VARCHAR(16),
    comorbidities TEXT,
    file_path TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

_UPSERT_SQL = """
INSERT INTO synthetic_corpus
    (doc_name, category, patient_age, patient_sex, severity, comorbidities, file_path)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (doc_name) DO UPDATE SET
    category = EXCLUDED.category,
    patient_age = EXCLUDED.patient_age,
    patient_sex = EXCLUDED.patient_sex,
    severity = EXCLUDED.severity,
    comorbidities = EXCLUDED.comorbidities,
    file_path = EXCLUDED.file_path;
"""


async def load_corpus(database_url: str, index_path: Path) -> int:
    """
    Upsert every corpus index entry into the synthetic_corpus table.

    Args:
        database_url: Neon PostgreSQL connection string.
        index_path: Path to corpus_index.json.

    Returns:
        int: Number of rows upserted.

    Raises:
        asyncpg.PostgresError: If the database is unreachable or the DDL/upsert fails.
        FileNotFoundError: If the corpus index does not exist.
    """
    with open(index_path, encoding="utf-8") as f:
        entries = json.load(f)

    conn = await asyncpg.connect(database_url)
    try:
        await conn.execute(_CREATE_TABLE_SQL)
        count = 0
        for entry in entries:
            # Entries written by the resume path of the generator carry only
            # file/category/variant - tolerate both shapes.
            variant = entry.get("variant", {})
            await conn.execute(
                _UPSERT_SQL,
                entry.get("doc_name") or Path(entry["file"]).stem,
                entry["category"],
                entry.get("patient_age") or variant.get("age"),
                entry.get("patient_sex") or variant.get("sex"),
                entry.get("severity") or variant.get("severity"),
                entry.get("comorbidities") or variant.get("comorbidities"),
                entry["file"],
            )
            count += 1
        return count
    finally:
        await conn.close()


def main() -> None:
    """Parse args, validate environment, and run the loader."""
    parser = argparse.ArgumentParser(description="Load synthetic corpus metadata into Neon")
    parser.add_argument(
        "--index",
        default="test-data/synthetic/corpus_index.json",
        help="Path to corpus_index.json",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        logger.error(
            "DATABASE_URL is not set in .env - cannot load corpus into Neon. "
            "Set it to your Neon PostgreSQL connection string and re-run."
        )
        sys.exit(1)

    index_path = Path(args.index)
    if not index_path.exists():
        logger.error(
            "Corpus index not found at %s - run scripts/generate_synthetic_corpus.py first.",
            index_path,
        )
        sys.exit(1)

    count = asyncio.run(load_corpus(database_url, index_path))
    logger.info("Done. %d corpus documents upserted into synthetic_corpus.", count)


if __name__ == "__main__":
    main()
