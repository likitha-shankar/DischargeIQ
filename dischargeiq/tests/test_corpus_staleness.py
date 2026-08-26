"""
Tests for corpus staleness detection in scripts/run_corpus_for_review.py.

The catch-up job decides whether to spend API calls based on this. Getting it
wrong is expensive in one direction and dishonest in the other: too eager and
it regenerates finished work forever, too lax and it declares the corpus
complete over outputs that describe a superseded system.

The second failure actually happened. On 25 Aug 2026 three agent prompts
changed and 54 outputs stayed on disk looking complete. The old catch-up
script counted only MISSING files, so it would have reported success over all
of them, and any accuracy report built from that corpus would have blended two
different systems while reading as a single measurement.
"""

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import run_corpus_for_review as runner  # noqa: E402 - path set up above


@pytest.fixture
def outputs(tmp_path, monkeypatch):
    """Point the runner at a throwaway output directory."""
    directory = tmp_path / "outputs"
    directory.mkdir()
    monkeypatch.setattr(runner, "_OUTPUT_DIR", directory)
    return directory


def _write(directory: Path, name: str, meta) -> Path:
    """Write one output file carrying the given _review_meta."""
    path = directory / f"{name}.json"
    path.write_text(json.dumps({"_review_meta": meta}))
    return path


class TestIsStale:
    """Anything we cannot vouch for counts as stale."""

    def test_current_prompt_stamp_is_not_stale(self, outputs):
        path = _write(outputs, "a", {"prompt_versions": runner.prompt_versions()})
        assert runner.is_stale(path) is False

    def test_superseded_prompt_stamp_is_stale(self, outputs):
        """The case that motivated all of this."""
        stamp = dict(runner.prompt_versions())
        stamp["agent4_system_prompt"] = "deadbeef"
        path = _write(outputs, "a", {"prompt_versions": stamp})
        assert runner.is_stale(path) is True

    def test_unstamped_output_is_stale(self, outputs):
        """
        Outputs written before stamping existed cannot be vouched for.

        Treating them as current would freeze the corpus in whatever state it
        happened to be in when stamping was added.
        """
        assert runner.is_stale(_write(outputs, "a", {})) is True

    def test_corrupt_output_is_stale(self, outputs):
        """A file we cannot read is not a file we can trust."""
        path = outputs / "a.json"
        path.write_text("{ not json")
        assert runner.is_stale(path) is True

    def test_missing_file_is_stale(self, outputs):
        assert runner.is_stale(outputs / "nope.json") is True


class TestCountStale:
    """The number the catch-up loop uses to decide whether to keep going."""

    def test_counts_missing_and_superseded_together(self, tmp_path, outputs):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        for name in ("a", "b", "c"):
            (corpus / f"{name}.pdf").write_bytes(b"%PDF-1.4")
        # a: current. b: superseded. c: no output at all.
        _write(outputs, "a", {"prompt_versions": runner.prompt_versions()})
        _write(outputs, "b", {"prompt_versions": {"agent4_system_prompt": "old"}})

        todo, total = runner.count_stale(corpus)
        assert (todo, total) == (2, 3)

    def test_all_current_reports_zero(self, tmp_path, outputs):
        """
        The no-op path cron depends on.

        A non-zero count here would make the scheduled job spend API calls
        every night forever on a corpus that is already finished.
        """
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "a.pdf").write_bytes(b"%PDF-1.4")
        _write(outputs, "a", {"prompt_versions": runner.prompt_versions()})

        assert runner.count_stale(corpus) == (0, 1)


class TestPromptVersions:
    """The stamp itself."""

    def test_covers_every_prompt_file(self):
        stems = {p.stem for p in (runner._PROMPT_DIR).glob("*.txt")}
        assert set(runner.prompt_versions()) == stems
        assert stems, "no prompt files found - the stamp would be vacuous"

    def test_is_stable_across_calls(self):
        """A hash that moved on its own would mark everything stale forever."""
        assert runner.prompt_versions() == runner.prompt_versions()
