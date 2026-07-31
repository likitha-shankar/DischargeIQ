"""
scripts/lock_corpus.py

Sprint 4, Task 4.4 - Version-lock a clinical-trial testing corpus.
Owner: Likitha Shankar.

Computes a SHA-256 for every PDF in the corpus directory, cross-checks the
set against its corpus_index.json, and writes a signed lockfile
(corpus_lock.json beside the PDFs). The lockfile is the frozen contract for
clinician review (Sprint 5): once locked, any change to a corpus PDF changes
its hash and `--verify` fails, so reviewers can trust that every score maps
to the exact document they saw.

Works on either corpus. The default remains test-data/synthetic so the
original locked hash reproduces; pass --corpus-dir test-data/mtsamples to
freeze the 106-document real corpus that replaced it as primary in July 2026.
Both index formats are handled - see _indexed_stems().

Usage:
  python scripts/lock_corpus.py                                  # synthetic
  python scripts/lock_corpus.py --corpus-dir test-data/mtsamples # MTSamples
  python scripts/lock_corpus.py --verify --corpus-dir <dir>      # drift check

--verify makes no writes and is safe to run in CI or before a review session.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Default kept as the original synthetic corpus so existing invocations and
# the locked hash under tag task-4.4-corpus-lock still reproduce. Pass
# --corpus-dir test-data/mtsamples to freeze the MTSamples corpus instead.
_DEFAULT_CORPUS_DIR = Path("test-data/synthetic")


def _index_path(corpus_dir: Path) -> Path:
    """Path to the corpus index for a corpus directory."""
    return corpus_dir / "corpus_index.json"


def _lockfile_path(corpus_dir: Path) -> Path:
    """Path to the lockfile for a corpus directory."""
    return corpus_dir / "corpus_lock.json"


def _indexed_stems(index_path: Path) -> set[str]:
    """
    Read the document stems listed in a corpus index.

    Two index shapes exist and both must lock. The synthetic generator writes
    a bare list of entries keyed by "doc_name"; build_mtsamples_corpus.py
    writes an object with a "documents" list keyed by "file" (with the .pdf
    suffix). Normalising here keeps one locker for both corpora.

    Args:
        index_path: Location of corpus_index.json.

    Returns:
        set[str]: Document stems, without the .pdf extension.

    Raises:
        FileNotFoundError: If the index is missing.
        ValueError: If the index matches neither known shape.
    """
    if not index_path.exists():
        raise FileNotFoundError(
            f"{index_path} not found - generate the corpus before locking it."
        )
    payload = json.loads(index_path.read_text())

    if isinstance(payload, list):
        return {entry["doc_name"] for entry in payload}
    if isinstance(payload, dict) and "documents" in payload:
        return {Path(entry["file"]).stem for entry in payload["documents"]}
    raise ValueError(
        f"Unrecognised corpus index shape in {index_path}: expected a list of "
        f"entries with 'doc_name', or an object with a 'documents' list."
    )


def _sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _current_state(corpus_dir: Path) -> dict:
    """
    Build the lock payload from the corpus on disk right now.

    Returns:
        dict with corpus_size, a sorted {filename: sha256} map, and a
        combined_hash (SHA-256 over the sorted per-file hashes) that is a
        single fingerprint for the whole corpus.

    Raises:
        FileNotFoundError: If the corpus directory or index is missing.
    """
    index_names = _indexed_stems(_index_path(corpus_dir))
    pdfs = sorted(corpus_dir.glob("*.pdf"))

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


def write_lock(corpus_dir: Path) -> str:
    """Write the lockfile from the current corpus. Returns the combined hash."""
    state = _current_state(corpus_dir)
    state["locked_at"] = datetime.now(timezone.utc).isoformat()
    _lockfile_path(corpus_dir).write_text(json.dumps(state, indent=2) + "\n")
    return state["combined_hash"]


def verify_lock(corpus_dir: Path) -> bool:
    """
    Compare the current corpus against the lockfile.

    Returns:
        True when the corpus is unchanged since it was locked; False on any
        drift (changed, added, or removed file) or a missing lockfile.
    """
    lockfile = _lockfile_path(corpus_dir)
    if not lockfile.exists():
        print("No lockfile - run without --verify to create one.", file=sys.stderr)
        return False
    locked = json.loads(lockfile.read_text())
    current = _current_state(corpus_dir)
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
    parser = argparse.ArgumentParser(description="Version-lock a testing corpus")
    parser.add_argument(
        "--verify", action="store_true",
        help="Exit 1 if the corpus drifted from the lockfile (no writes).",
    )
    parser.add_argument(
        "--corpus-dir", type=Path, default=_DEFAULT_CORPUS_DIR,
        help=f"Corpus directory to lock (default: {_DEFAULT_CORPUS_DIR}).",
    )
    args = parser.parse_args()

    if args.verify:
        if verify_lock(args.corpus_dir):
            print("Corpus matches the lockfile - clean.")
            sys.exit(0)
        print("Corpus DRIFTED from the lockfile.", file=sys.stderr)
        sys.exit(1)

    combined = write_lock(args.corpus_dir)
    print(f"Locked {_lockfile_path(args.corpus_dir)} - combined_hash {combined[:16]}...")


if __name__ == "__main__":
    main()
