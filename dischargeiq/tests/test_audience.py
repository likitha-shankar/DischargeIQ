"""
Tests audience detection and its effect on Agent 2's user message.

The bug this covers: a 10-month-old's discharge summary produced "Your ears
have an infection", addressed to an infant. The reader is a parent. Detection
runs on raw document text because Agent 1's locked schema has no age field.

The false-positive direction matters more than the false-negative one, so the
adult cases here are the load-bearing ones: misreading an adult document as
pediatric would tell a grown patient about "your child's" condition.
"""

import pytest

from dischargeiq.agents.diagnosis_agent import _build_user_message
from dischargeiq.agents.escalation_agent import _build_user_message as _escalation_message
from dischargeiq.agents.medication_agent import _build_user_message as _med_message_raw
from dischargeiq.agents.recovery_agent import _build_user_message as _recovery_message
from dischargeiq.models.extraction import ExtractionOutput, Medication
from dischargeiq.models.pipeline import PipelineResponse
from dischargeiq.services.chat import ChatService
from dischargeiq.utils.case_audio import build_dialogue_script
from dischargeiq.utils.audience import (
    AUDIENCE_CAREGIVER,
    AUDIENCE_PATIENT,
    audience_instruction,
    detect_audience,
)


def _med_message(extraction, audience):
    """Agent 3 takes safety_context second, so audience must go by keyword."""
    return _med_message_raw(extraction, audience=audience)


@pytest.mark.parametrize(
    "text",
    [
        "The patient is a 10-month-old male who was seen in the office.",
        "The patient is a 3-week-old female admitted with fever.",
        "The patient is an 11 year old boy with severe ear pain.",
        "This 2-day-old newborn was discharged in stable condition.",
        "Newborn male discharged home with parents.",
    ],
)
def test_pediatric_documents_get_caregiver_voice(text):
    """Young patients switch the addressee to whoever is caring for them."""
    assert detect_audience(text) == AUDIENCE_CAREGIVER


@pytest.mark.parametrize(
    "text",
    [
        "The patient is a 68-year-old male with heart failure.",
        "The patient is a 45 year old woman admitted for COPD.",
        "The patient is a 16-year-old male treated for a fracture.",
        "The patient is an 88-year-old female after hip replacement.",
    ],
)
def test_adult_documents_keep_patient_voice(text):
    """Adults, and adolescents who read their own summary, are addressed directly."""
    assert detect_audience(text) == AUDIENCE_PATIENT


def test_missing_or_ageless_text_defaults_to_patient():
    """No age information must never flip the voice - default is prior behaviour."""
    assert detect_audience("") == AUDIENCE_PATIENT
    assert detect_audience("Discharge summary. Condition stable.") == AUDIENCE_PATIENT


def test_child_mentioned_late_does_not_flip_an_adult_document():
    """
    Only the opening of the document is searched.

    An adult's summary that mentions a child later (social history, family
    history) must stay in the patient voice.
    """
    text = (
        "The patient is a 52-year-old female admitted with chest pain. "
        + "Hospital course was uneventful. " * 60
        + "Social history: she cares for her 4-year-old grandson at home."
    )
    assert detect_audience(text) == AUDIENCE_PATIENT


def test_implausible_age_is_ignored():
    """A nonsense age is not a basis for choosing an addressee."""
    assert detect_audience("Device implanted 900 years old per record.") == (
        AUDIENCE_PATIENT
    )


def test_instruction_is_empty_for_patient_audience():
    """The patient voice is the prompt default, so it costs no extra tokens."""
    assert audience_instruction(AUDIENCE_PATIENT) == ""


def test_caregiver_instruction_reaches_agent2_user_message():
    """The detected audience must actually appear in what Agent 2 is sent."""
    extraction = ExtractionOutput(primary_diagnosis="Bilateral otitis media")

    caregiver_message = _build_user_message(extraction, AUDIENCE_CAREGIVER)
    assert "AUDIENCE:" in caregiver_message
    assert "your child" in caregiver_message.lower()
    # Clinical content still present and still first among the data lines.
    assert "Bilateral otitis media" in caregiver_message

    patient_message = _build_user_message(extraction, AUDIENCE_PATIENT)
    assert "AUDIENCE:" not in patient_message
    assert patient_message.startswith("Primary diagnosis:")


def test_agent2_default_argument_is_unchanged_behaviour():
    """Callers that never pass an audience keep the original message exactly."""
    extraction = ExtractionOutput(primary_diagnosis="Heart failure")
    assert _build_user_message(extraction) == _build_user_message(
        extraction, AUDIENCE_PATIENT
    )


# ── Agents 3, 4, 5 ────────────────────────────────────────────────────────────
#
# All four patient-facing agents must switch voice together. A document where
# Agent 2 says "your child's ears" while Agent 4 says "your recovery" is worse
# than one that is uniformly wrong, because the reader cannot tell who each
# section is about.

_AGENT_MESSAGE_BUILDERS = [
    pytest.param(_med_message, id="agent3_medication"),
    pytest.param(_recovery_message, id="agent4_recovery"),
    pytest.param(_escalation_message, id="agent5_escalation"),
]


@pytest.fixture
def full_extraction():
    """An extraction populated enough for every agent's message builder."""
    return ExtractionOutput(
        primary_diagnosis="Bilateral otitis media",
        secondary_diagnoses=["Fever"],
        medications=[Medication(name="Omnicef", dose="125 mg/5 mL")],
        red_flag_symptoms=["Trouble breathing", "Increased lethargy"],
        activity_restrictions=["No swimming for one week"],
    )


@pytest.mark.parametrize("build", _AGENT_MESSAGE_BUILDERS)
def test_caregiver_instruction_reaches_every_agent(build, full_extraction):
    """Each of Agents 3-5 receives the audience line when it applies."""
    message = build(full_extraction, AUDIENCE_CAREGIVER)
    assert "AUDIENCE:" in message
    assert "your child" in message.lower()
    # Clinical grounding must survive the prefix.
    assert "Bilateral otitis media" in message


@pytest.mark.parametrize("build", _AGENT_MESSAGE_BUILDERS)
def test_patient_audience_leaves_every_agent_message_unchanged(
    build, full_extraction
):
    """The default path must be byte-identical to the pre-change behaviour."""
    message = build(full_extraction, AUDIENCE_PATIENT)
    assert "AUDIENCE:" not in message
    assert message.startswith("Primary diagnosis:")


# ── Post-pipeline surfaces: chat, audio narration ─────────────────────────────
#
# These read the audience off the PipelineResponse rather than the raw document,
# because by the time they run the document text is long gone. If the field did
# not survive onto the response, chat would contradict the tabs.

def test_audience_defaults_to_patient_on_the_response_model():
    """Older stored responses without the field must not flip voice."""
    response = PipelineResponse(
        extraction=ExtractionOutput(primary_diagnosis="Heart failure"),
        diagnosis_explanation="",
        medication_rationale="",
        recovery_trajectory="",
        escalation_guide="",
        fk_scores={},
        extraction_warnings=[],
        pipeline_status="complete",
    )
    assert response.audience == AUDIENCE_PATIENT


def test_chat_prompt_gains_caregiver_override():
    """Chat must switch voice, and the override must come after the default."""
    context = {"extraction": {}, "audience": AUDIENCE_CAREGIVER}
    prompt = ChatService._build_system_prompt(context)

    assert "WHO YOU ARE TALKING TO" in prompt
    assert "your child" in prompt.lower()
    # The template's default instruction must be overridden, not merely present:
    # last instruction wins, so the override has to sit after it.
    assert prompt.index("WHO YOU ARE TALKING TO") > prompt.index("Use 'you' and 'your'")


def test_chat_prompt_unchanged_for_adult_patient():
    """No audience, or the patient audience, leaves the prompt as it was."""
    assert "WHO YOU ARE TALKING TO" not in ChatService._build_system_prompt(
        {"extraction": {}}
    )
    assert "WHO YOU ARE TALKING TO" not in ChatService._build_system_prompt(
        {"extraction": {}, "audience": AUDIENCE_PATIENT}
    )


def test_audio_narration_receives_audience_without_breaking_empty_check():
    """
    The narration payload carries the audience, and the emptiness guard still
    fires. Adding an always-populated key to `sections` would otherwise make
    the "nothing to narrate" check unreachable.
    """
    with pytest.raises(ValueError, match="no content to narrate"):
        build_dialogue_script({"extraction": {}, "audience": AUDIENCE_CAREGIVER})
