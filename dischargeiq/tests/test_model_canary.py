"""
Detecting a model change behind a pinned name.

`gemini-2.5-flash-lite` is a floating alias. Google can move the served
checkpoint without the name changing, and probing the API on 10 Sep 2026
showed there is nothing to read: `system_fingerprint` comes back empty and
`response.model` echoes the request. So `docs/MODEL_VERSIONING.md` documents a
re-evaluation trigger on version change, and no version exists to trigger on.

The canary substitutes behaviour for a version string. Five runs of the same
probe at temperature 0 produced one distinct output, which is what makes a
changed digest a signal rather than noise.

The tests that matter here are not about hashing. They are:
  - the committed baseline contains no corpus text
  - the probes are synthetic, not copied from a patient document
  - a changed reply is visible, not merely counted
"""

import json
import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))

from model_canary import _PROBES, _digest  # noqa: E402

_BASELINE = _REPO / "evaluation" / "model_canary.json"

#: Drug names that appear in the corpus. Any of these in a committed probe or
#: baseline means clinical text reached the repository.
_CORPUS_DRUGS = [
    "furosemide", "lovenox", "niacin", "coumadin", "celebrex", "synthroid",
    "percocet", "toprol", "trazodone", "colace", "lisinopril", "carvedilol",
]


class TestTheProbesAreSynthetic:
    """
    The first draft of this canary used a medication line copied verbatim from
    mtsamples_026. Committing it would have put de-identified corpus text in
    the repository - the exact mistake that made this repo's history a problem
    on 6 Sep 2026. These tests exist so that cannot come back.
    """

    def test_no_probe_quotes_a_corpus_document(self):
        joined = " ".join(_PROBES.values()).lower()
        found = [d for d in _CORPUS_DRUGS if d in joined]
        assert not found, f"probe text contains corpus drug names: {found}"

    def test_the_committed_baseline_carries_no_corpus_text(self):
        if not _BASELINE.exists():
            pytest.skip("no baseline frozen")
        raw = _BASELINE.read_text().lower()
        found = [d for d in _CORPUS_DRUGS if d in raw]
        assert not found, f"baseline contains corpus drug names: {found}"

    def test_the_baseline_stays_small_enough_to_read_in_a_diff(self):
        """
        It is committed, so a reviewer has to be able to see a change. A
        baseline that grows into a wall of text stops being reviewable and
        becomes a file people scroll past.
        """
        if not _BASELINE.exists():
            pytest.skip("no baseline frozen")
        assert len(_BASELINE.read_text()) < 8000


class TestTheBaselineIsUsable:
    def test_every_probe_has_a_digest_and_a_reply(self, ):
        if not _BASELINE.exists():
            pytest.skip("no baseline frozen")
        baseline = json.loads(_BASELINE.read_text())
        for name, entry in (baseline.get("probes") or {}).items():
            assert entry.get("digest"), f"{name} has no digest"
            # The reply is what turns "something changed" into "this changed".
            # A digest alone is an alarm nobody can act on.
            assert "reply" in entry, f"{name} stored no reply to compare against"

    def test_the_baseline_names_the_model_it_describes(self):
        if not _BASELINE.exists():
            pytest.skip("no baseline frozen")
        baseline = json.loads(_BASELINE.read_text())
        assert baseline.get("model"), "baseline does not say which model it is for"

    def test_digests_are_digests(self):
        if not _BASELINE.exists():
            pytest.skip("no baseline frozen")
        baseline = json.loads(_BASELINE.read_text())
        for name, entry in (baseline.get("probes") or {}).items():
            assert re.fullmatch(r"[0-9a-f]{16}", entry["digest"]), name


class TestTheDigest:
    def test_whitespace_does_not_change_it(self):
        """
        Model replies vary in line breaks and indentation without meaning
        anything different. A canary that fires on reformatting is noise.
        """
        assert _digest('["a",\n  "b"]') == _digest('["a", "b"]')

    def test_different_content_changes_it(self):
        assert _digest('["a", "b"]') != _digest('["a", "c"]')

    def test_a_dropped_item_changes_it(self):
        """The behaviour the 10 Sep regression showed: an item going missing."""
        assert _digest('["a", "b", "c"]') != _digest('["a", "b"]')

    def test_empty_is_handled(self):
        assert _digest("") == _digest("   ")


class TestTheProbesCoverWhatMatters:
    def test_there_is_a_list_extraction_probe(self):
        """
        The behaviour that regressed on 10 Sep was reading every item from one
        comma-separated list. If the canary does not probe that, it would not
        have caught the thing that prompted it.
        """
        assert "list_extraction" in _PROBES

    def test_there_is_an_absence_probe(self):
        """Refusing to supply a value that is not there is the core safety
        property of the whole pipeline."""
        assert "absent_field" in _PROBES

    def test_every_probe_is_short_enough_to_be_cheap(self):
        for name, prompt in _PROBES.items():
            assert len(prompt) < 400, f"{name} is too long to run routinely"
