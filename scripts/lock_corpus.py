"""
scripts/lock_corpus.py

Sprint 4, Task 4.4 - Version-lock the 50-document synthetic clinical-trial
corpus. Owner: Likitha Shankar.

Computes a SHA-256 for every PDF in test-data/synthetic/, cross-checks the
set against corpus_index.json, and writes a signed lockfile
(test-data/synthetic/corpus_lock.json). The lockfile is the frozen contract
for clinician review (Sprint 5): once locked, any change to a corpus PDF
changes its hash and `--verify` fails, so reviewers can trust that every
score maps to the exact document they saw.

Usage:
  python scripts/lock_corpus.py            # write/refresh the lockfile
  python scripts/lock_corpus.py --verify   # fail (exit 1) if anything drifted

--verify makes no writes and is safe to run in CI or before a review session.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_CORPUS_DIR = Path("test-data/synthetic")
_INDEX = _CORPUS_DIR / "corpus_index.json"
_LOCKFILE = _CORPUS_DIR / "corpus_lock.json"


def _sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _current_state() -> dict:
    """
    Build the lock payload from the corpus on disk right now.

    Returns:
        dict with corpus_size, a sorted {filename: sha256} map, and a
        combined_hash (SHA-256 over the sorted per-file hashes) that is a
        single fingerprint for the whole corpus.

    Raises:
        FileNotFoundError: If the corpus directory or index is missing.
    """
    if not _INDEX.exists():
        raise FileNotFoundError(
            f"{_INDEX} not found - run scripts/generate_synthetic_corpus.py first."
        )
    index_names = {entry["doc_name"] for entry in json.loads(_INDEX.read_text())}
    pdfs = sorted(_CORPUS_DIR.glob("*.pdf"))

    file_hashes = {p.name: _sha256(p) for p in pdfs}
    # Cross-check: every indexed doc must have a PDF and vice versa, so a
    # silently added or dropped file cannot slip into a "locked" corpus.
    pdf_stems = {p.stem for p in pdfs}
    missing = sorted(index_names - pdf_stems)
    extra = sorted(pdf_stems - index_names)
    if missing or extra:
        raise ValueError(
            f"Corpus/index mismatch - missing PDFs: {missing}; "
            f"unindexed PDFs: {extra}. Fix before locking."
        )

    combined = hashlib.sha256(
        "".join(f"{name}:{h}" for name, h in sorted(file_hashes.items())).encode()
    ).hexdigest()
    return {
        "corpus_size": len(pdfs),
        "combined_hash": combined,
        "files": dict(sorted(file_hashes.items())),
    }


def write_lock() -> str:
    """Write the lockfile from the current corpus. Returns the combined hash."""
    state = _current_state()
    state["locked_at"] = datetime.now(timezone.utc).isoformat()
    _LOCKFILE.write_text(json.dumps(state, indent=2) + "\n")
    return state["combined_hash"]


def verify_lock() -> bool:
    """
    Compare the current corpus against the lockfile.

    Returns:
        True when the corpus is unchanged since it was locked; False on any
        drift (changed, added, or removed file) or a missing lockfile.
    """
    if not _LOCKFILE.exists():
        print("No lockfile - run without --verify to create one.", file=sys.stderr)
        return False
    locked = json.loads(_LOCKFILE.read_text())
    current = _current_state()
    if locked["combined_hash"] == current["combined_hash"]:
        return True
    # Report exactly what drifted so a reviewer knows which scores to redo.
    locked_files, current_files = locked["files"], current["files"]
    for name in sorted(set(locked_files) | set(current_files)):
        old, new = locked_files.get(name), current_files.get(name)
        if old != new:
            state = "removed" if new is None else ("added" if old is None else "changed")
            print(f"  {state}: {name}", file=sys.stderr)
    return False


def main() -> None:
    """Write or verify the corpus lockfile."""
    parser = argparse.ArgumentParser(description="Version-lock the synthetic corpus")
    parser.add_argument(
        "--verify", action="store_true",
        help="Exit 1 if the corpus drifted from the lockfile (no writes).",
    )
    args = parser.parse_args()

    if args.verify:
        if verify_lock():
            print("Corpus matches the lockfile - clean.")
            sys.exit(0)
        print("Corpus DRIFTED from the lockfile.", file=sys.stderr)
        sys.exit(1)

    combined = write_lock()
    print(f"Locked {_LOCKFILE} - combined_hash {combined[:16]}...")


if __name__ == "__main__":
    main()
