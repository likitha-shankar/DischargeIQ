"""
File: dischargeiq/ingest/__init__.py
Owner: Likitha Shankar
Description: Public surface of the document ingest layer (DIS-O1). Callers
  import extract_document_text and IngestResult from here, never from the
  internal modules, so the internals can evolve (OCR route) without churn.
Used by: dischargeiq/pipeline/orchestrator.py, tests.
"""

from dischargeiq.ingest.models import IngestResult
from dischargeiq.ingest.reader import extract_document_text

__all__ = ["IngestResult", "extract_document_text"]
