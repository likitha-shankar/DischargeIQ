"""
Prose content for the DischargeIQ clinical review brief.

Every string the reader sees lives here so the brief can be reworded without
touching the Word-rendering logic in build_clinical_brief_docx.py. Clinical
figures come from the 106-document de-identified corpus or from the shipped
pipeline; section 9 bounds what the prototype is and is not.
"""

ABSTRACT = (
    "DischargeIQ takes the paperwork a patient is handed on the way out of the hospital and makes "
    "it readable. It rewrites the patient's own discharge document into plain language, answers "
    "their questions using nothing but that document, and separately reports what the document "
    "never explained so a care team can close the gap. Every clinical judgement stays with a "
    "human: the app explains what was already decided, and does not decide anything itself."
)

PROBLEM_INTRO = (
    "Patients are discharged with paperwork written for clinicians and billing systems, then "
    "asked to manage their own recovery from it. Comprehension is low, and the documents "
    "themselves are frequently incomplete. Across our 106-document de-identified corpus, warning "
    "signs appear in only 34% of documents, discharge medications in 62%, and follow-up "
    "instructions in 69%."
)

PROBLEM_BULLETS = [
    "Patients often cannot tell which instruction is urgent and which is routine.",
    "Explanations must reflect the patient's actual document, not a generic template for their diagnosis.",
    "The system must communicate uncertainty clearly and never present AI output as medical advice.",
    "Gaps in the discharge document itself must surface to a human, not be silently filled by the AI.",
]

WHAT_IT_DOES_INTRO = (
    "DischargeIQ combines document extraction, plain-language explanation, and gap detection to "
    "support two primary use cases:"
)

WHAT_IT_DOES_ROWS = [
    (
        "Patient Companion",
        "Turns the discharge document into seven plain-language views: what happened, medications "
        "and why each was prescribed, recovery timeline, warning signs, follow-up appointments, a "
        "teach-back quiz, and a grounded chat that answers only from the document. Its purpose is "
        "to help a patient leave knowing what to do and what to watch for.",
    ),
    (
        "AI Patient Simulator",
        "Reads the same document as a confused patient would and lists the questions the document "
        "does not answer, graded critical / moderate / minor with an overall gap score. Its purpose "
        "is to surface documentation gaps to a care coordinator or nurse before the patient is "
        "left alone with the paperwork.",
    ),
]

HOW_IT_WORKS = [
    "The patient uploads or photographs their discharge document.",
    "A router agent checks the document is a discharge summary at all and rejects bills, "
    "explanation-of-benefit forms, and invoices before any clinical agent runs.",
    "An extraction agent pulls structured fields - diagnosis, medications, appointments, "
    "restrictions, red-flag symptoms - and returns null rather than guessing any field the "
    "document does not contain.",
    "Four explanation agents run in parallel over that structured extraction: diagnosis, "
    "medication rationale, recovery timeline, and a three-tier escalation guide.",
    "A readability gate scores every output on Flesch-Kincaid and targets grade 6 or below.",
    "The patient simulator agent re-reads the document and reports what it never answered.",
    "The patient can take a five-question teach-back quiz before and after reading; the "
    "before/after delta is the comprehension measure we report.",
]

TECHNICAL_INTRO = (
    "DischargeIQ is designed as more than a general-purpose chatbot. The prototype separates "
    "document extraction, clinical explanation, safety rules, and gap detection into distinct "
    "components, so that each can be inspected and constrained independently."
)

TECHNICAL_ROWS = [
    (
        "Extraction Contract",
        "A locked structured schema is the single contract between the document and every "
        "downstream agent. Fields absent from the document are returned as null. No downstream "
        "agent ever sees the raw document, only what was verifiably extracted from it.",
    ),
    (
        "Grounding Check",
        "Every medication, dose, and diagnosis in the output is checked back against the source "
        "text. Content that does not trace to the document is flagged rather than shipped.",
    ),
    (
        "Explanation Agents",
        "Four specialised agents write the patient-facing sections from the extraction, each "
        "scoped to only the fields it needs and each blocked from clinical advice outside its "
        "remit.",
    ),
    (
        "Escalation Layer",
        "Warning signs are presented in three tiers - call 911, go to the emergency department "
        "today, call your doctor - with a hard rule of zero ambiguous language. Every escalation "
        "output is read manually before it ships.",
    ),
    (
        "Gap Detection",
        "The simulator agent scores what the document failed to explain and routes it to a human. "
        "The AI surfaces the gap; a clinician decides what to do about it.",
    ),
    (
        "Readability Gate",
        "All patient-facing text is scored with Flesch-Kincaid against a grade 6 target, and "
        "failures send the prompt back for revision rather than reaching the patient.",
    ),
]

SAFETY_BOUNDARIES = [
    "DischargeIQ will not diagnose any condition, and will not interpret a symptom the patient reports.",
    "It will not prescribe, change, adjust, or recommend stopping any medication. It explains why a "
    "drug was prescribed and never touches what the patient should take.",
    "It will not answer from general medical knowledge. The chat answers only from the uploaded "
    "document and refuses everything else.",
    "It will identify red-flag situations and direct the patient toward emergency services or their "
    "care team rather than handling them conversationally.",
    "It will distinguish supportive explanation from medical advice, and label any content that did "
    "not come from the patient's own document.",
    "It will communicate uncertainty when a document is incomplete or ambiguous rather than filling "
    "the gap.",
    "Gaps it detects are framed as items to discuss with the care team, never as findings.",
]

VALIDATION_INTRO = (
    "Validation combines a structured clinician review of system output against source documents "
    "with a measured comprehension study. The purpose is to establish whether the plain-language "
    "output is faithful to the document it came from, and whether patients understand more after "
    "reading it."
)

VALIDATION_BULLETS = [
    "A 106-document corpus of real de-identified discharge documents drives testing, alongside a "
    "locked 50-document synthetic corpus for reproducible evaluation.",
    "Clinician reviewers score output for fidelity to the source document rather than against an "
    "ideal summary, because real discharge paperwork is itself incomplete.",
    "Any medication, dose, or diagnosis appearing in the output but not in the source is treated as "
    "the serious failure, and is checked automatically on every run as well as by reviewers.",
    "Comprehension is measured by a before-and-after teach-back quiz generated from the patient's "
    "own document, not from a question bank.",
    "No real patient data is used. Every test document is synthetic or de-identified.",
]

SOURCES = [
    (
        "AHRQ Re-Engineered Discharge (RED) Toolkit",
        "Used to inform which discharge elements matter most to patient understanding and to "
        "post-discharge safety.",
        "https://www.ahrq.gov/patient-safety/settings/hospital/red/toolkit/index.html",
    ),
    (
        "AHRQ Health Literacy Universal Precautions Toolkit - Teach-Back Method",
        "Used as the basis for the teach-back quiz design and for the wording of the "
        "self-assessment rungs.",
        "https://www.ahrq.gov/health-literacy/improve/precautions/tool5.html",
    ),
    (
        "MTSamples de-identified transcribed medical reports",
        "Source of the 106-document real-world discharge corpus used for extraction and "
        "hallucination testing.",
        "https://mtsamples.com/",
    ),
]

STATUS_ROWS = [
    (
        "Product scope",
        "Refined to a focused, pilot-ready patient-facing workflow: upload, seven plain-language "
        "views, grounded chat, and teach-back quiz.",
    ),
    (
        "Software",
        "End-to-end pipeline is implemented and deployed. Mobile application is the primary "
        "surface; a web demo surface runs the same backend.",
    ),
    (
        "Corpus",
        "106 real de-identified documents plus a locked 50-document synthetic corpus, both wired "
        "into automated testing.",
    ),
    (
        "Clinician review",
        "Review rubric and reviewer portal are built. Reviewer recruitment and the pass bar remain "
        "open and are the subject of question 5 below.",
    ),
    (
        "Patient validation",
        "Teach-back quiz loop is shipped and instrumented. A patient-facing pilot has not started "
        "and depends on the governance answers in question 5.",
    ),
]

QUESTIONS_INTRO = (
    "Below are the five decisions I cannot make without clinical authority. Each is a call I own as "
    "product lead, each is currently shipped one way, and each will change what we build depending "
    "on the answer. I have deliberately left out anything the team can settle itself, and anything "
    "about models, hosting, or architecture."
)

QUESTIONS = [
    (
        "Which parts of a discharge document should we explain first, because patients most often "
        "misunderstand them or come to harm from misunderstanding them?",
        [
            (
                "The decision I own:",
                "the reading order of the seven tabs, and which topics the teach-back quiz weights "
                "most heavily.",
            ),
            (
                "Shipped today:",
                "all sections carry equal weight, and the patient can reorder them by choosing a "
                "topic they most want to understand. Warning signs are the one section never "
                "dropped from the quiz, whatever they choose.",
            ),
            (
                "What changes:",
                "if some content is more dangerous when misunderstood, it moves ahead of patient "
                "choice and joins the protected list. That list is one line of prompt text - the "
                "question is which topics belong on it.",
            ),
        ],
    ),
    (
        "What should the app show when a discharge document lists no warning signs at all - which "
        "is the case in roughly two-thirds of the real documents we hold?",
        [
            (
                "The decision I own:",
                "whether to show a safety net the document did not provide, or to show nothing.",
            ),
            (
                "Shipped today:",
                "a short general emergency list - chest pain, trouble breathing, heavy bleeding, "
                "fainting, sudden weakness - labelled plainly as general advice and not from the "
                "patient's document. Where a document does list warning signs, they are presented "
                "in three tiers: call 911, go to the emergency department today, call your doctor.",
            ),
            (
                "What changes:",
                "if any non-document clinical content crosses a line, we ship an empty state and "
                "the 34% becomes a finding we report rather than a gap we fill. I would also value "
                "your read on whether three tiers is the right structure, or whether there is a "
                "symptom class where tiering is itself unsafe and the app should only say 911.",
            ),
        ],
    ),
    (
        "What patient and document information is genuinely essential for personalising the "
        "explanation, and what should we stop collecting?",
        [
            (
                "The decision I own:",
                "what the app stores about a patient, and what it asks them for.",
            ),
            (
                "Shipped today:",
                "the document itself, an age band so that a summary belonging to a child is written "
                "to the caregiver rather than addressing the child as \"you\", the topic the patient "
                "says they want to understand, and an optional daily mood check-in that softens what "
                "the app asks of them on a bad day. Everything is stored on the phone.",
            ),
            (
                "What changes:",
                "anything you call unnecessary comes out. I would rather cut a feature now than "
                "defend the data collection at a privacy review later.",
            ),
        ],
    ),
    (
        "How should the app communicate uncertainty when the document is incomplete, ambiguous, or "
        "contradicts itself - and is refusal the right behaviour at 2am?",
        [
            (
                "The decision I own:",
                "what the app says when it does not know, and what the chat does with a question it "
                "cannot answer.",
            ),
            (
                "Shipped today:",
                "the extraction omits rather than infers, so a field absent from the document stays "
                "empty. The chat answers only from the uploaded document; asked anything else, "
                "including an urgent symptom question, it refuses and redirects to the warning-signs "
                "section and the emergency line.",
            ),
            (
                "What changes:",
                "if refusal plus redirect is too passive for a sick person typing at 2am, that "
                "interaction needs to be designed rather than defaulted, and I need to know what it "
                "should do instead.",
            ),
        ],
    ),
    (
        "What evidence and success measures would you expect before this is safe to put in front of "
        "patients?",
        [
            (
                "The decision I own:",
                "what the clinician review measures, where its pass bar sits, and what we call "
                "sufficient evidence to run a pilot.",
            ),
            (
                "Shipped today:",
                "reviewers score output for fidelity to the source document rather than against an "
                "ideal summary, on the reasoning that real discharge paperwork is itself incomplete. "
                "Content in the output that is not in the source is treated as the serious failure "
                "and is also checked automatically on every run. Comprehension is measured by a "
                "five-question quiz taken before and after reading.",
            ),
            (
                "What I need specifically:",
                "whether fidelity-to-source is the right instruction or absent content should count "
                "against us; where the pass bar belongs; whether a five-question before-and-after "
                "delta credibly stands in for teach-back as you practise it; and which approvals - "
                "IRB, legal, BAA, clinical governance - actually gate a patient-facing pilot, and in "
                "what order. A bar changed after scoring is not evidence, so I need this before the "
                "review starts, not after.",
            ),
        ],
    ),
]

CLOSING = (
    "If it is more useful, I am happy to walk through the app live rather than on paper - the "
    "screens above are the ones the questions refer to. What I most want to hear is the answer I "
    "was not hoping for: the single thing that would make you stop trusting this output."
)

LIMITATIONS = (
    "Stating the limits plainly, because the questions above only make sense against them. "
    "DischargeIQ has never been used by a real patient. It has no regulatory clearance and is not "
    "a medical device, and nothing in it is a route to urgent care - a patient in trouble needs "
    "911, not this app. Its comprehension numbers come from instrumented testing on our own "
    "corpus, not from a study, and should not be quoted as clinical evidence. It reads English "
    "only. It can explain a document well and still be explaining a document that was wrong to "
    "begin with, which is the failure mode I am least able to detect on my own. What I am trying "
    "to establish this quarter is narrow: is the output faithful to its source, and what would "
    "have to be true before a patient could safely be given it."
)

