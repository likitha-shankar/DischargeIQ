"""
Scoring extraction against clinician annotations.

The tool this tests has no data yet - no document has been annotated. That is
exactly when the scoring logic should be pinned down: the first real
annotations will arrive with a clinician's time attached, and discovering then
that the matcher counts "Lasix" and "furosemide" as two errors would waste
that time and, worse, produce a number somebody might report.

The failure this guards against is directional. Naive string equality reports
one MISS and one EXTRA for the same drug written two ways - two errors where
there is none, and both in the direction that makes the system look worse than
it is. An evaluation that is wrong in the flattering direction gets caught; one
wrong in the harsh direction gets believed.
"""

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))

from score_against_gold import (  # noqa: E402
    normalise_dose,
    normalise_drug,
    score_appointments,
    score_document,
    score_medications,
    score_warnings,
    wilson,
)


def med(name, dose=None):
    return {"name": name, "dose": dose}


class TestDrugNameMatching:
    @pytest.mark.parametrize("a,b", [
        ("Lasix", "furosemide"),
        ("Lasix 40mg", "furosemide 40 mg"),
        ("Furosemide", "furosemide tablet"),
        ("Coreg", "carvedilol"),
        ("Metoprolol ER 25 mg", "metoprolol"),
        ("fluticasone/salmeterol", "fluticasone-salmeterol"),
        ("  LISINOPRIL  ", "lisinopril"),
        ("Warfarin (Coumadin)", "warfarin"),
    ])
    def test_the_same_drug_written_two_ways_matches(self, a, b):
        assert normalise_drug(a) == normalise_drug(b), f"{a!r} vs {b!r}"

    @pytest.mark.parametrize("a,b", [
        ("furosemide", "metformin"),
        ("metoprolol", "metformin"),
        ("aspirin", "atorvastatin"),
    ])
    def test_different_drugs_do_not_match(self, a, b):
        """
        The failure that would matter most: collapsing two real drugs into one
        hides a genuine omission behind a matcher that is too forgiving.
        """
        assert normalise_drug(a) != normalise_drug(b)

    def test_a_nameless_entry_normalises_to_nothing(self):
        assert normalise_drug("") == ""
        assert normalise_drug("   ") == ""


class TestDoses:
    @pytest.mark.parametrize("a,b", [
        ("40mg", "40 mg"),
        ("40MG", "40mg"),
        ("40 mg ", "40mg"),
    ])
    def test_spacing_and_case_are_not_a_dose_difference(self, a, b):
        assert normalise_dose(a) == normalise_dose(b)

    def test_a_real_dose_difference_is_reported_separately(self):
        """
        Not a recall failure - the drug was found. Counted on its own because
        a silently wrong dose is arguably worse than a missing drug: the
        patient acts on it.
        """
        result = score_medications([med("Furosemide", "40 mg")],
                                   [med("Furosemide", "20 mg")])
        assert result["dose_mismatch"]
        assert not result["system_miss"]
        assert not result["matched"]

    def test_a_missing_dose_on_either_side_is_not_a_mismatch(self):
        """A document that never stated a dose is not a disagreement about it."""
        assert not score_medications([med("Furosemide", "40 mg")],
                                     [med("Furosemide")])["dose_mismatch"]
        assert not score_medications([med("Furosemide")],
                                     [med("Furosemide", "40 mg")])["dose_mismatch"]


class TestTheCategoriesStaySeparate:
    def test_a_drug_the_system_missed_is_a_system_miss(self):
        result = score_medications([med("Furosemide"), med("Aspirin")],
                                   [med("Furosemide")])
        assert result["system_miss"] == ["aspirin (no dose)"]
        assert result["matched"] == ["furosemide"]

    def test_an_extra_drug_is_never_called_a_fabrication(self):
        """
        The tool cannot know whether an extra entity is invented or simply
        something the annotator missed. Only a human can, so this category is
        named for review and never scored as an error.
        """
        result = score_medications([med("Furosemide")],
                                   [med("Furosemide"), med("Aspirin")])
        assert result["system_extra"] == ["aspirin (no dose)"]
        assert "fabrication" not in str(result).lower()

    def test_brand_and_generic_produce_neither_a_miss_nor_an_extra(self):
        """
        The whole point. Two errors where there is none, both in the
        unflattering direction.
        """
        result = score_medications([med("Lasix", "40 mg")],
                                   [med("furosemide", "40mg")])
        assert result["matched"] == ["furosemide"]
        assert not result["system_miss"]
        assert not result["system_extra"]


class TestAppointments:
    def test_a_relative_date_is_compared_as_written(self):
        """
        The schema forbids the annotator resolving "in 2 weeks" to a calendar
        date, because Agent 1 is forbidden to. Resolving on one side only
        would score correct behaviour as wrong.
        """
        gold = [{"specialty": "Cardiology", "date": "in 2 weeks"}]
        found = [{"specialty": "Cardiology", "date": "in 2 weeks"}]
        assert score_appointments(gold, found)["matched"]

    def test_a_different_date_is_a_miss_and_an_extra(self):
        gold = [{"specialty": "Cardiology", "date": "2026-04-05"}]
        found = [{"specialty": "Cardiology", "date": "2026-04-12"}]
        result = score_appointments(gold, found)
        assert result["system_miss"] and result["system_extra"]
        assert not result["matched"]

    def test_provider_stands_in_when_specialty_is_absent(self):
        gold = [{"provider": "Dr. Chen", "date": "2 weeks"}]
        found = [{"provider": "dr chen", "date": "2 weeks"}]
        assert score_appointments(gold, found)["matched"]

    def test_an_entry_with_nothing_identifying_is_dropped(self):
        assert not score_appointments([{"date": ""}], [{"date": ""}])["matched"]


class TestWarningSigns:
    def test_wording_differences_still_match(self):
        result = score_warnings([{"text": "swelling in the legs"}],
                                ["leg swelling that gets worse"])
        assert result["matched"]

    def test_a_sign_that_vanished_entirely_is_caught(self):
        """The risk worth catching: a red flag the document listed and the
        system dropped."""
        result = score_warnings(
            [{"text": "coughing up blood"}], ["swelling in the legs"])
        assert result["system_miss"] == ["coughing up blood"]

    def test_common_words_alone_do_not_create_a_match(self):
        """
        Otherwise "call your doctor if you have any new pain" matches every
        warning sign ever written, and omission becomes invisible - which is
        the failure the whole exercise exists to measure.
        """
        result = score_warnings([{"text": "call your doctor if you have any"}],
                                ["call your doctor about the new swelling"])
        assert result["system_miss"], "matched on stopwords alone"


class TestConfidenceIntervals:
    def test_a_small_sample_gives_a_wide_interval(self):
        low, high = wilson(19, 20)
        assert high - low > 15

    def test_a_larger_sample_narrows_it(self):
        small = wilson(19, 20)
        large = wilson(475, 500)
        assert (large[1] - large[0]) < (small[1] - small[0])

    def test_it_never_exceeds_one_hundred_percent(self):
        """
        The reason for Wilson rather than the normal approximation: at
        proportions near 1 with small n, the normal interval runs past 100%
        and a report claims better-than-perfect recall.
        """
        low, high = wilson(20, 20)
        assert high <= 100.0 and low >= 0.0

    def test_no_data_claims_nothing(self):
        assert wilson(0, 0) == (0.0, 100.0)


class TestWholeDocumentScoring:
    def test_a_perfect_extraction_scores_clean(self):
        annotation = {
            "medications": [med("Furosemide", "40 mg")],
            "follow_up_appointments": [{"specialty": "Cardiology", "date": "2026-04-05"}],
            "warning_signs": [{"text": "swelling in the legs"}],
        }
        output = {"extraction": {
            "medications": [med("Lasix", "40mg")],
            "follow_up_appointments": [{"specialty": "cardiology", "date": "2026-04-05"}],
            "red_flag_symptoms": ["swelling in the legs"],
        }}
        scores = score_document(annotation, output)
        for category, block in scores.items():
            assert not block["system_miss"], f"{category}: {block['system_miss']}"
            assert not block["dose_mismatch"], category

    def test_an_empty_extraction_reports_every_entity_as_missed(self):
        """The total-failure case must not score as clean by default."""
        annotation = {
            "medications": [med("Furosemide"), med("Aspirin")],
            "follow_up_appointments": [],
            "warning_signs": [{"text": "coughing up blood"}],
        }
        scores = score_document(annotation, {"extraction": {}})
        assert len(scores["medications"]["system_miss"]) == 2
        assert len(scores["warning_signs"]["system_miss"]) == 1

    def test_a_missing_extraction_block_does_not_crash(self):
        assert score_document({}, {}) is not None


class TestNothingVanishesFromTheArithmetic:
    """
    The bug this class exists for was found by adding up a synthetic run and
    noticing seven annotated medications had become six.

    zip() paired gold against extracted entries under the same drug key and
    dropped the surplus on either side. The extra entry was neither matched
    nor missed - it left the arithmetic entirely. An entity disappearing
    without trace is the exact failure the whole exercise measures, so it must
    not happen inside the measuring tool. A recall figure computed from a
    denominator that quietly shrank is worse than no figure.
    """

    def _accounted(self, result: dict) -> int:
        return (len(result["matched"]) + len(result["system_miss"])
                + len(result["dose_mismatch"]))

    def test_a_drug_annotated_twice_but_extracted_once(self):
        """
        Legitimate and real: metoprolol 25 mg in the morning, 50 mg at night.
        The second annotated entry must surface as a miss, not evaporate.
        """
        gold = [med("Metoprolol", "25 mg"), med("Metoprolol", "50 mg")]
        result = score_medications(gold, [med("Metoprolol", "25 mg")])
        assert self._accounted(result) == len(gold)
        assert result["system_miss"] == ["metoprolol (50 mg)"]

    def test_a_drug_extracted_twice_but_annotated_once(self):
        """The mirror case: the surplus is a review item, not a silent drop."""
        found = [med("Metoprolol", "25 mg"), med("Metoprolol", "50 mg")]
        result = score_medications([med("Metoprolol", "25 mg")], found)
        assert result["system_extra"] == ["metoprolol (50 mg)"]

    @pytest.mark.parametrize("gold_count,found_count", [
        (1, 1), (2, 1), (1, 2), (3, 1), (1, 3), (2, 2), (3, 2),
    ])
    def test_every_gold_entry_is_always_accounted_for(self, gold_count, found_count):
        gold = [med("Metoprolol", f"{i + 1} mg") for i in range(gold_count)]
        found = [med("Metoprolol", f"{i + 1} mg") for i in range(found_count)]
        result = score_medications(gold, found)
        assert self._accounted(result) == gold_count, (
            f"{gold_count} annotated, {self._accounted(result)} accounted for"
        )

    def test_the_same_holds_when_names_differ_in_form(self):
        gold = [med("Lasix", "40 mg"), med("Furosemide", "20 mg")]
        result = score_medications(gold, [med("furosemide", "40mg")])
        assert self._accounted(result) == 2
