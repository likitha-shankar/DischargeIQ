"""
DischargeIQ — FastAPI entry point.

Defines the REST API for the DischargeIQ multi-agent pipeline.
Endpoints:
  - GET  /health   → liveness check
  - POST /analyze  → accepts a discharge PDF, runs the agent pipeline

Dependencies: FastAPI, python-dotenv; delegates processing to
dischargeiq.pipeline.orchestrator.run_pipeline.
"""

import logging
import os
import tempfile

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile

from dischargeiq.pipeline.orchestrator import run_pipeline

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="DischargeIQ",
    description="Multi-agent AI system for plain-language patient discharge education",
    version="0.1.0",
)


@app.get("/health")
async def health():
    """Liveness probe — returns 200 with {"status": "ok"} if the server is running."""
    return {"status": "ok"}


@app.post("/analyze")
async def analyze_discharge(file: UploadFile = File(...)):
    """
    Accept a discharge PDF upload and run the multi-agent pipeline.

    Writes the uploaded file to a temp location and passes the path to
    run_pipeline(), which returns a PipelineResponse.

    Args:
        file: PDF file uploaded by the patient or clinician.

    Returns:
        dict: Serialized PipelineResponse (extraction, agent outputs, FK scores).

    Raises:
        HTTPException 400: If the uploaded file is not a PDF.
        HTTPException 500: If an unexpected error occurs during processing.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    try:
        contents = await file.read()
    except Exception as read_error:
        logger.error("Failed to read uploaded file: %s", read_error)
        raise HTTPException(status_code=500, detail="Failed to read uploaded file.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        result = run_pipeline(tmp_path)
        return result.model_dump()
    except Exception as pipeline_error:
        logger.error("Pipeline error for document %s: %s", file.filename, pipeline_error)
        raise HTTPException(status_code=500, detail="Internal pipeline error.")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
