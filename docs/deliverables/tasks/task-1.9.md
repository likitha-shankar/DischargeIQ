# Task 1.9 - Grounded Chatbot on Mobile ✅

**Deliverable:** the patient can ask plain-language questions about their own
discharge document and get answers drawn only from that document.

**Files:** `dischargeiq_mobile/lib/widgets/chat_sheet.dart` (mobile surface),
`dischargeiq/api/routes/chat.py` and `dischargeiq/services/chat.py`
(server). `POST /chat` takes `message`, `session_id` and `pipeline_context`.

**What "grounded" means here:** the answer is constrained to the extraction
already produced for that session. The model is not asked what it knows about
a condition; it is asked what this patient's document says.

**The hardening that made it real** (`9df24ce`): an anonymous caller could
previously supply their own `pipeline_context` and have it answered as though
it were a real patient's extraction. That turned a grounded endpoint into a
general-purpose one, which is exactly the property the feature exists to
prevent. Callers without a key can no longer invent their own context.

**Related:** `c79b342` added the voice companion in the chat.

**Demo:** on the phone, after an analysis, open the chat and ask something the
document answers ("what is furosemide for?") and something it does not ("can I
drink alcohol?"). The second should decline rather than answer from general
knowledge - that contrast is the point of the feature and is worth showing
deliberately.

**Tests:** `dischargeiq/tests/test_chat_grounding.py`.
