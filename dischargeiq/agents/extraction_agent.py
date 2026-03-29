"""
Agent 1 — Extraction agent (DIS-5).

Reads discharge document text (from pdfplumber) and calls the LLM with
agent1_system_prompt.txt to produce JSON matching ExtractionOutput.
Validates with Pydantic; never fabricates fields — missing values are null or [].

This file is a stub until DIS-5 implements run_extraction_agent().
"""

