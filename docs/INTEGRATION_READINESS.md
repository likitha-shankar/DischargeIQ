# DischargeIQ - Integration-Readiness Documentation

**Sprint 6, Task 6.3.** How the standalone summer build maps to a future EHR
integration. No integration happens this summer and no dates are committed
here; this documents that the architecture was built componentized so the
mapping is possible later.

## 1. Architectural rule: componentization

The summer deliverable is a standalone app that needs no EHR to run. Every
backend interface is a plug-in boundary, so the same pipeline can later be
fed by an EHR instead of a phone camera without rewriting the agents.

The seam is deliberately narrow:

```
[ input source ] -> raw document text (str) -> [ pipeline ] -> PipelineResponse (JSON)
```

Anything that can produce discharge-document text and consume the response
JSON can drive DischargeIQ. Today the input source is a PDF upload or
on-device OCR; tomorrow it could be an EHR document feed.

## 2. The componentized endpoints (HTTP contract)

All under the FastAPI app (`/api/*` behind nginx on Cloud Run). Auth-gated
routes require the `verify_api_key` dependency.

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET  | `/health` | Liveness (`/api/health` behind nginx) | no |
| POST | `/analyze` | Multipart PDF upload -> full pipeline | yes |
| POST | `/analyze/text` | Pre-extracted text -> full pipeline (OCR / **EHR seam**) | yes |
| POST | `/chat` | Grounded Q&A over one session's pipeline output | no (CORS) |
| POST | `/quiz/generate` | 5 teach-back MCQs from extraction (stateless) | no |
| POST | `/quiz/score` | Grade one phase, return comprehension delta | no |
| GET  | `/media/{document_type}` | Per-diagnosis audio explainer (404 = none yet) | no |
| GET  | `/media/{document_type}/video` | Per-diagnosis video explainer | no |
| GET  | `/pdf/{session_id}` | Stored PDF bytes for the viewer | no |
| GET  | `/progress/{session_id}` | Live pipeline progress for the loading UI | no |

**The EHR seam is `POST /analyze/text`.** It already accepts raw document
text (built for on-device OCR) and runs the identical pipeline lifecycle as
the PDF path. An EHR adapter would call this endpoint with the discharge
document text; no agent, prompt, or model code changes.

## 3. The output schema (the integration contract)

`PipelineResponse` (`dischargeiq/models/pipeline.py`) is the stable JSON an
EHR would consume. Field names are the locked contract - see CLAUDE.md,
"Agent 1 JSON output schema (LOCKED)".

```
PipelineResponse
├─ extraction: ExtractionOutput      # structured fields (diagnosis, meds, appts, ...)
├─ diagnosis_explanation: str        # Agent 2, plain language
├─ medication_rationale: str         # Agent 3, per-drug
├─ recovery_trajectory: str          # Agent 4, week-by-week
├─ escalation_guide: str             # Agent 5, three-tier warning signs
├─ fk_scores: dict                   # Flesch-Kincaid grade per agent output
├─ extraction_warnings: list
├─ pipeline_status: "complete" | "complete_with_warnings" | "partial" | "rejected"
├─ rejection_reason: str | None      # set only when status == "rejected"
├─ document_type: str                # router label - drives media selection
└─ patient_simulator: PatientSimulatorOutput | None   # Agent 6 gap analysis
```

`extraction` (`ExtractionOutput`) is the structured layer an EHR maps to
discrete fields; the five agent strings are the patient-facing layer. Both
travel in one response so a consumer picks what it needs.

## 4. HIPAA / BAA deployment runbook (Vertex AI path)

Real patient data must be processed only under BAA coverage. The code path
is already shipped (`b2e07b2`); this is the operator runbook to activate it.

### 4.1 Two data modes, one env var

| Mode | `LLM_PROVIDER` | Auth | Use for |
|---|---|---|---|
| Synthetic / dev | `gemini` | `GOOGLE_API_KEY` (plain API key) | synthetic corpus, testing |
| **Real patient data** | `vertex` | ADC / service account | any real PHI (BAA-covered) |

Switching modes is one env var, no code change. `vertex` serves the same
Gemini models inside a GCP project a BAA can cover.

### 4.2 Activate the Vertex (BAA) path

1. Execute a BAA with Google Cloud covering Vertex AI for the target GCP project.
2. Enable the Vertex AI API in that project.
3. Set env:
   ```
   LLM_PROVIDER=vertex
   LLM_MODEL=google/gemini-2.5-flash-lite   # note the google/ prefix
   VERTEX_PROJECT=<your-gcp-project-id>
   VERTEX_LOCATION=us-central1
   ```
4. Auth:
   - Local: `gcloud auth application-default login`
   - Cloud Run: attach a service account with the Vertex AI User role
     (ADC is picked up automatically; no key file in the image).
5. Confirm `/api/health` reports the vertex provider and run one synthetic
   document end to end before pointing any real data at it.

### 4.3 PHI handling rules (already enforced in code)

- Raw document text and free-text agent output are **never** written to the
  database. Only structured fields, hashes, and metadata persist
  (`db/history.py`; CLAUDE.md Neon schema rule).
- In-memory PDF/session stores are process-local `OrderedDict`s - under
  `max-instances > 1` a `/pdf/{session_id}` may 404 on a different instance.
  Production PHI deployment needs GCS or Redis for shared session state
  (known gap; not wired this summer).
- Fallback provider on the PHI path must also be BAA-covered, or set
  `LLM_FALLBACK_PROVIDER=none` so a failure degrades to `partial` rather
  than sending PHI to a non-covered provider.

## 5. What is explicitly NOT built this summer

- No EHR integration (Epic, Athena, TheraCareAI) - named only as the
  direction the architecture supports.
- No shared-state session store (GCS/Redis) for multi-instance PHI serving.
- No local/open-source model migration; no predictive analytics or risk
  scoring; no storage of raw scans, raw text, or PHI.
