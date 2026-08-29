"""
Guards the in-app licence attribution against drifting from reality.

The app shows an open-source licence page (LOF review action item, 26 Aug
2026). Flutter collects Dart package licences automatically, but the Python
backend is invisible to that collector, so those entries are hand-maintained
in dischargeiq_mobile/lib/services/backend_licenses.dart.

Hand-maintained means wrong eventually, and it was wrong immediately. The
first draft listed google-cloud-texttospeech and google-cloud-aiplatform,
NEITHER of which is installed - Vertex and Cloud TTS are reached over REST
with google-auth. It also carried approximate versions ("FastAPI 0.115" when
0.136.1 is pinned). Both are worse than saying nothing: a compliance artefact
that looks authoritative and is not invites exactly the scrutiny it should
survive.

These tests run without a device, because they read the Dart source as text.
"""

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_LICENSES = _REPO / "dischargeiq_mobile" / "lib" / "services" / "backend_licenses.dart"
_LOCKFILE = _REPO / "requirements.lock.txt"


def _declared() -> dict[str, str]:
    """Package name -> version as declared to patients on the licence page."""
    source = _LICENSES.read_text(encoding="utf-8")
    pairs = re.findall(r"name: '([^']+)'.*?version: '([^']+)'", source, re.S)
    # "openai (python)" on the page is the "openai" distribution.
    return {name.split(" ")[0].lower().replace("_", "-"): ver for name, ver in pairs}


def _locked() -> dict[str, str]:
    """Package name -> version from the production lockfile."""
    locked = {}
    for line in _LOCKFILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        locked[name.strip().lower().replace("_", "-")] = version.strip()
    return locked


class TestVersionsAreReal:
    """Every version shown to a patient must be one we actually ship."""

    def test_declared_versions_match_the_lockfile(self):
        declared, locked = _declared(), _locked()
        overlap = set(declared) & set(locked)
        assert overlap, "no packages in common - the parser is probably broken"
        wrong = {
            name: (declared[name], locked[name])
            for name in sorted(overlap)
            if declared[name] != locked[name]
        }
        assert not wrong, (
            "licence page version does not match requirements.lock.txt "
            f"(declared, locked): {wrong}"
        )

    def test_no_package_is_invented(self):
        """
        The failure that actually happened.

        Two google-cloud client libraries were listed that the project does
        not install. Attribution for software you do not ship is not a
        harmless extra; it is a false statement in a compliance document.
        """
        locked = _locked()
        # Transitive dependencies are legitimately absent from the lockfile,
        # so only flag names that look like direct dependencies we invented.
        known_transitive = {"pdfminer.six", "pypdfium2", "pyphen"}
        for name in _declared():
            if name in known_transitive:
                continue
            assert name in locked, (
                f"{name!r} appears on the licence page but is not in "
                "requirements.lock.txt. If it is transitive, add it to "
                "known_transitive; if it is not installed at all, remove it."
            )


class TestTheAwkwardOneIsShown:
    """A page listing only comfortable dependencies is not attribution."""

    def test_pyphen_is_disclosed_with_its_tri_license(self):
        source = _LICENSES.read_text(encoding="utf-8")
        assert "Pyphen" in source
        # The whole point is that the GPL option exists and is NOT taken.
        assert "GPL" in source and "MPL" in source

    def test_apache_and_no_network_copyleft_are_stated(self):
        source = _LICENSES.read_text(encoding="utf-8")
        assert "Apache License 2.0" in source
        assert "AGPL" in source, "the banned category should be named explicitly"


class TestTheLimitationIsStated:
    """
    The page carries attributions, not full licence texts.

    MIT, BSD and Apache-2.0 all require reproducing their text in a
    distribution. Saying so in the file is what stops a future reader assuming
    this is finished before a store release.
    """

    @pytest.mark.parametrize("phrase", ["LIMITATION", "full licence text"])
    def test_limitation_is_documented(self, phrase):
        assert phrase in _LICENSES.read_text(encoding="utf-8")
