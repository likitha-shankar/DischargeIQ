"""
DischargeIQ — FastAPI entry point.

Defines the REST API for the DischargeIQ multi-agent pipeline.
Endpoints:
  - GET  /health   → liveness check
  - POST /analyze  → accepts a discharge PDF, runs the agent pipeline

Dependencies: FastAPI, python-dotenv, hashlib (stdlib).
The /analyze endpoint will delegate to pipeline/orchestrator.py once agents are built.
"""

import os
import tempfile
import hashlib
import logging

from fastapi import FastAPI, File, UploadFile, HTTPException
from dotenv import load_dotenv

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

    Writes the uploaded file to a temp location, computes a SHA-256 hash for
    deduplication, and (once wired) passes the file to the orchestrator.

    Args:
        file: PDF file uploaded by the patient or clinician.

    Returns:
        dict: Pipeline results including extraction, explanations, and FK scores.

    Raises:
        HTTPException 400: If the uploaded file is not a PDF.
        HTTPException 500: If an unexpected error occurs during processing.
    """
    # Validate file type before processing
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    try:
        contents = await file.read()
    except Exception as read_error:
        logger.error("Failed to read uploaded file: %s", read_error)
        raise HTTPException(status_code=500, detail="Failed to read uploaded file.")

    # Write to a temp file so downstream agents can use pdfplumber on a file path
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        doc_hash = hashlib.sha256(contents).hexdigest()

        # Pipeline not yet wired — return placeholder until orchestrator is built
        return {
            "pipeline_status": "not_implemented",
            "document_hash": doc_hash,
            "message": "Pipeline agents are not yet implemented. Upload accepted.",
        }
    except Exception as pipeline_error:
        logger.error("Pipeline error for document %s: %s", file.filename, pipeline_error)
        raise HTTPException(status_code=500, detail="Internal pipeline error.")
    finally:
        # Always clean up the temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
