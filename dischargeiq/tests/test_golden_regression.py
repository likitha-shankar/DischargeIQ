"""
The golden-file regression, as a suite gate.

`scripts/golden_regression.py` is the human-facing tool. This runs the same
comparison inside pytest so drift fails a test run rather than waiting for
somebody to remember the script exists.

Two properties are tested here that the script cannot test about itself:

  - the committed manifest carries NO clinical text. The entire design rests
    on that being true, since the corpus outputs it derives from are
    gitignored under the program rule. Asserting it in a comment is not
    enough; the repo's history already shows what happens when clinical
    content reaches a commit by accident.
  - the comparison actually detects the regressions it claims to. A drift
    check that silently passes is worse than none, because it reads as
    evidence.

Skips cleanly when the corpus is absent - it is gitignored, so a fresh clone
has no outputs to check.
"""

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))

from golden_regression import (  # noqa: E402
    _compare,
    _digest,
    manifest_carries_no_clinical_text,
    summarise,
)

_MANIFEST = _REPO / "evaluation" / "golden_manifest.json"
_OUTPUTS = _REPO / "evaluation" / "corpus_outputs"


@pytest.fixture(scope="module")
def manifest() -> dict:
    if not _MANIFEST.exists():
        pytest.skip("no golden manifest; run scripts/golden_regression.py --freeze")
    return json.loads(_MANIFEST.read_text())


@pytest.fixture(scope="module")
def outputs() -> dict:
    if not _OUTPUTS.exists():
        pytest.skip("no corpus outputs present (gitignored)")
    found = {}
    for path in sorted(_OUTPUTS.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if payload.get("pipeline_status") in ("complete", "complete_with_warnings"):
            found[path.stem] = payload
    if not found:
        pytest.skip("no completed corpus outputs")
    return found


class TestTheManifestIsSafeToCommit:
    """
    The committed artefact must carry counts, statuses and digests - never a
    medication name, a date, or a symptom.
    """

    def test_no_free_text_anywhere_in_the_manifest(self, manifest):
        offenders = manifest_carries_no_clinical_text(manifest)
        assert not offenders, (
            f"{len(offenders)} manifest value(s) are free text and must not "
            f"be committed: {offenders[:5]}"
        )

    @pytest.mark.parametrize("term", [
        "furosemide", "lisinopril", "carvedilol", "insulin", "aspirin",
        "chest pain", "shortness of breath", "mg", "Dr.",
    ])
    def test_known_clinical_terms_are_absent(self, term):
        """
        A second, independent check that does not share the allow-list logic
        above. If both the allow-list and this miss something, they are
        unlikely to miss it the same way.
        """
        if not _MANIFEST.exists():
            pytest.skip("no golden manifest")
        assert term.lower() not in _MANIFEST.read_text().lower()

    def test_digests_are_digests(self, manifest):
        for doc_id, entry in manifest.items():
            for name, value in (entry.get("digests") or {}).items():
                assert len(value) == 16 and all(c in "0123456789abcdef" for c in value), (
                    f"{doc_id}.{name} is not a hex digest: {value!r}"
                )


class TestTheCorpusHasNotDrifted:
    def test_every_frozen_document_still_matches(self, manifest, outputs):
        drifted = {}
        for doc_id, expected in manifest.items():
            if doc_id not in outputs:
                continue  # covered separately below
            drift = _compare(doc_id, expected, summarise(outputs[doc_id]))
            if drift:
                drifted[doc_id] = drift
        assert not drifted, (
            f"{len(drifted)} document(s) drifted from the golden baseline. "
            f"Run scripts/golden_regression.py for the detail, and re-freeze "
            f"ONLY after confirming each change was intended. "
            f"First: {list(drifted.items())[:2]}"
        )

    def test_no_frozen_document_has_vanished(self, manifest, outputs):
        missing = [doc_id for doc_id in manifest if doc_id not in outputs]
        assert not missing, (
            f"{len(missing)} frozen document(s) produce no completed output "
            f"any more: {missing[:5]}"
        )


class TestTheCheckWouldActuallyCatchSomething:
    """
    Guards the guard, on synthetic payloads rather than the real corpus.
    Every case below is a regression that reached production in some form.
    """

    def _payload(self, **overrides) -> dict:
        base = {
            "pipeline_status": "complete",
            "document_type": "heart_failure",
            "source_stratum": "dictated",
            "extraction": {
                "medications": [{"name": "Furosemide", "dose": "40 mg"}],
                "follow_up_appointments": [{"specialty": "Cardiology", "date": "2026-04-05"}],
                "red_flag_symptoms": ["weight gain"],
                "secondary_diagnoses": [],
                "procedures_performed": [],
            },
            "diagnosis_explanation": "x",
            "medication_rationale": "x",
            "recovery_trajectory": "x",
            "escalation_guide": "CALL 911 IMMEDIATELY\nGO TO THE ER TODAY\nCALL YOUR DOCTOR",
            "fk_scores": {"agent3_medication": 5.0},
        }
        base.update(overrides)
        return base

    def _drift_for(self, mutate) -> list[str]:
        before = summarise(self._payload())
        payload = self._payload()
        mutate(payload)
        return _compare("synthetic", before, summarise(payload))

    def test_a_dropped_medication_is_caught(self):
        drift = self._drift_for(
            lambda p: p["extraction"]["medications"].clear())
        assert any("medications" in line for line in drift)

    def test_a_substituted_dose_is_caught_even_though_the_count_holds(self):
        """
        The quiet one. A count-only check passes here, and a dose silently
        changing matters as much as a drug disappearing.
        """
        def mutate(p):
            p["extraction"]["medications"][0]["dose"] = "999 mg"
        drift = self._drift_for(mutate)
        assert any("count unchanged" in line for line in drift), drift

    def test_a_missing_911_route_is_caught(self):
        def mutate(p):
            p["escalation_guide"] = "Call your doctor if you feel unwell."
        drift = self._drift_for(mutate)
        assert any("911" in line for line in drift), drift

    def test_an_emptied_patient_facing_section_is_caught(self):
        def mutate(p):
            p["recovery_trajectory"] = "   "
        drift = self._drift_for(mutate)
        assert any("recovery_trajectory" in line for line in drift), drift

    def test_a_moved_appointment_date_is_caught(self):
        def mutate(p):
            p["extraction"]["follow_up_appointments"][0]["date"] = "2026-09-09"
        drift = self._drift_for(mutate)
        assert any("appointments" in line for line in drift), drift

    def test_a_status_downgrade_is_caught(self):
        drift = self._drift_for(
            lambda p: p.update({"pipeline_status": "partial"}))
        assert any("pipeline_status" in line for line in drift)

    def test_reordering_entities_is_NOT_drift(self):
        """
        The false-positive side. Extraction order is not meaningful, and a
        check that fires on it would be switched off within a week.
        """
        payload = self._payload()
        payload["extraction"]["medications"] = [
            {"name": "Aspirin", "dose": "81 mg"},
            {"name": "Furosemide", "dose": "40 mg"},
        ]
        before = summarise(payload)
        payload["extraction"]["medications"].reverse()
        assert _compare("synthetic", before, summarise(payload)) == []

    def test_rewording_prose_is_NOT_drift(self):
        """
        The reason this is not an exact-match golden file: regenerating an
        unchanged document produces different words every time.
        """
        def mutate(p):
            p["diagnosis_explanation"] = "Completely different wording here."
        assert self._drift_for(mutate) == []

    def test_a_small_readability_move_is_NOT_drift(self):
        def mutate(p):
            p["fk_scores"]["agent3_medication"] = 5.4
        assert self._drift_for(mutate) == []

    def test_a_large_readability_move_IS_drift(self):
        def mutate(p):
            p["fk_scores"]["agent3_medication"] = 9.0
        assert any("fk" in line for line in self._drift_for(mutate))


class TestTheDigestItself:
    def test_normalisation_ignores_case_and_spacing(self):
        assert _digest(["Furosemide  40 MG"]) == _digest(["furosemide 40 mg"])

    def test_different_content_gives_a_different_digest(self):
        assert _digest(["furosemide 40 mg"]) != _digest(["furosemide 20 mg"])

    def test_empty_and_blank_entries_do_not_count(self):
        assert _digest(["a", "", "   "]) == _digest(["a"])
