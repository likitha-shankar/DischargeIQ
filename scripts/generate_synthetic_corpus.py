"""
scripts/generate_synthetic_corpus.py

Sprint 1, Task 1.5 - Synthetic data generation.
Owner: Likitha Shankar

Generates 50 de-identified synthetic hospital discharge summaries:
  10 per diagnosis × 5 categories = 50 documents.

Categories:
  heart_failure  - ACC/AHA guidelines
  copd           - GOLD 2024
  diabetes       - ADA 2024
  hip_replacement - AAOS
  surgical       - ACC/ACS perioperative (laparoscopic)

Each document is generated with:
  - Realistic 11th-grade medical jargon (as clinicians actually write)
  - Disjointed formatting (mixed headers, inconsistent structure, abbreviations)
  - Synthetic patient demographics (no real PHI)
  - Different severities, comorbidities, and medication regimens per variant

Saves PDFs to test-data/synthetic/<category>_<nn>.pdf and records structured
metadata (primary_diagnosis, medications list, key fields) to
test-data/synthetic/corpus_index.json for Neon ingestion.

Usage:
  cd /path/to/DischargeIQ
  python scripts/generate_synthetic_corpus.py [--count 50] [--out test-data/synthetic]

Requires: GOOGLE_API_KEY (or current LLM_PROVIDER key) in .env
          reportlab (already in requirements.txt)
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from dischargeiq.utils.llm_client import call_chat_with_fallback, get_llm_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Generation configuration ──────────────────────────────────────────────────

_CATEGORIES = [
    "heart_failure",
    "copd",
    "diabetes",
    "hip_replacement",
    "surgical",
]

_DOCS_PER_CATEGORY = 10

# Variant seeds ensure 10 different documents per category - different
# patient age/sex, severity, comorbidities, and medication regimens.
_VARIANTS: list[dict] = [
    {"age": 68, "sex": "Male",   "severity": "moderate",  "comorbidities": "hypertension, CKD stage 3"},
    {"age": 74, "sex": "Female", "severity": "severe",    "comorbidities": "atrial fibrillation, obesity"},
    {"age": 55, "sex": "Male",   "severity": "mild",      "comorbidities": "type 2 diabetes, hyperlipidemia"},
    {"age": 81, "sex": "Female", "severity": "severe",    "comorbidities": "dementia, osteoporosis"},
    {"age": 62, "sex": "Male",   "severity": "moderate",  "comorbidities": "COPD, peripheral artery disease"},
    {"age": 49, "sex": "Female", "severity": "mild",      "comorbidities": "hypothyroidism, anxiety"},
    {"age": 77, "sex": "Male",   "severity": "moderate",  "comorbidities": "anemia, chronic pain"},
    {"age": 58, "sex": "Female", "severity": "severe",    "comorbidities": "heart failure, sleep apnea"},
    {"age": 70, "sex": "Male",   "severity": "mild",      "comorbidities": "gout, benign prostatic hyperplasia"},
    {"age": 65, "sex": "Female", "severity": "moderate",  "comorbidities": "rheumatoid arthritis, GERD"},
]

_SYSTEM_PROMPT = """You are a hospital discharge summary generator for clinical AI testing.

Generate a realistic hospital discharge summary that:
1. Uses authentic 11th-grade medical jargon exactly as a clinician would write
2. Has DISJOINTED formatting - mix of paragraph prose, bullet lists, tabular medication lists,
   inconsistent section headers (some ALL-CAPS, some Title Case, some missing entirely)
3. Includes realistic abbreviations (BID, PRN, q.d., EF, SpO2, SOB, DOE, etc.)
4. Is 400–600 words in the body (not counting headers)
5. MUST include these sections (in any order, with varied header names):
   - Patient demographics (synthetic only - no real names/DOB/MRN)
   - Primary diagnosis and relevant secondary diagnoses
   - Brief hospital course (procedures, key events)
   - Discharge medications (name, dose, frequency, duration - at least 4 medications)
   - Follow-up appointments (at least 2, with date placeholder like "in 2 weeks" or "06/30/2026")
   - Activity restrictions or weight-bearing status
   - Dietary restrictions if applicable
   - RED FLAG symptoms / when to seek emergency care
   - Discharge condition (Stable / Fair / Good)

CRITICAL: This is SYNTHETIC test data only. Use ONLY:
  - Fake patient names like "Patient A", "J. Doe", or "Test Patient [nn]"
  - Placeholder MRN like "MRN: 000-TEST-[nn]"
  - No real hospital names - use "General Hospital" or "Metro Medical Center"

Return ONLY the discharge summary text. No preamble, no explanation."""


def _build_user_message(category: str, variant: dict, index: int) -> str:
    """Build a variant-specific generation prompt for one discharge summary."""
    category_context = {
        "heart_failure": (
            "congestive heart failure (CHF) with reduced ejection fraction. "
            "Include: ejection fraction percentage, BNP level, diuretic therapy, "
            "ACEI/ARB or ARNI, beta-blocker, fluid restriction, daily weight monitoring."
        ),
        "copd": (
            "COPD exacerbation. "
            "Include: FEV1/FVC ratio or GOLD stage, O2 saturation, inhaler regimen "
            "(LAMA, LABA, ICS), systemic steroids taper, pulmonology follow-up."
        ),
        "diabetes": (
            "diabetes mellitus (Type 2) with hyperglycemic episode or complication. "
            "Include: admission glucose, HbA1c, insulin regimen or oral agents, "
            "glucose monitoring schedule, endocrinology follow-up, foot care."
        ),
        "hip_replacement": (
            "elective total hip arthroplasty (THA). "
            "Include: cemented vs uncemented, weight-bearing status (TTWB/PWB/WBAT), "
            "hip precautions (no >90° flexion, no internal rotation), DVT prophylaxis, "
            "PT/OT orders, wound care."
        ),
        "surgical": (
            "laparoscopic abdominal procedure (appendectomy, cholecystectomy, or hernia repair). "
            "Include: laparoscopic vs converted-to-open, trocar sites, post-op diet "
            "(clear liquids → regular), wound care, lifting restrictions, GI follow-up."
        ),
    }

    return (
        f"Generate discharge summary #{index} for a {variant['age']}-year-old {variant['sex']} "
        f"admitted for {category_context[category]} "
        f"Comorbidities: {variant['comorbidities']}. "
        f"Disease severity: {variant['severity']}. "
        f"Use synthetic patient identifier: 'Patient {index:02d}'."
    )


def _text_to_pdf(text: str, out_path: Path) -> None:
    """Render plain-text discharge summary to a PDF using reportlab."""
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "body",
        parent=styles["Normal"],
        fontSize=11,
        leading=15,
        spaceAfter=6,
    )
    story = []
    for line in text.split("\n"):
        # Escape XML special chars for reportlab Paragraph.
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(safe if safe.strip() else "&nbsp;", body_style))
        if not safe.strip():
            story.append(Spacer(1, 4))
    doc.build(story)


def generate_corpus(out_dir: Path, provider: str, client, model: str) -> list[dict]:
    """
    Generate all 50 synthetic discharge summaries.

    Args:
        out_dir: Directory to write PDFs into.
        provider: LLM provider string for call_chat_with_fallback.
        client: OpenAI-compat client from get_llm_client().
        model: Model name string.

    Returns:
        list[dict]: Corpus index entries (one per generated document).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    corpus_index = []
    global_idx = 1

    for category in _CATEGORIES:
        logger.info("Generating category: %s", category)
        for variant_idx, variant in enumerate(_VARIANTS):
            doc_name = f"{category}_{variant_idx + 1:02d}"
            out_path = out_dir / f"{doc_name}.pdf"

            if out_path.exists():
                logger.info("  Skipping %s - already exists", doc_name)
                corpus_index.append({"file": str(out_path), "category": category, "variant": variant})
                global_idx += 1
                continue

            user_msg = _build_user_message(category, variant, global_idx)
            logger.info("  Generating %s (variant %d)...", doc_name, variant_idx + 1)

            try:
                text = call_chat_with_fallback(
                    client=client,
                    model_name=model,
                    system_prompt=_SYSTEM_PROMPT,
                    user_message=user_msg,
                    max_tokens=900,
                    provider=provider,
                    agent_name="SyntheticCorpusGenerator",
                    document_id=doc_name,
                )
                _text_to_pdf(text, out_path)
                logger.info("  Saved: %s", out_path)
                corpus_index.append({
                    "file": str(out_path),
                    "category": category,
                    "variant_index": variant_idx,
                    "patient_age": variant["age"],
                    "patient_sex": variant["sex"],
                    "severity": variant["severity"],
                    "comorbidities": variant["comorbidities"],
                    "doc_name": doc_name,
                })
            except Exception as exc:
                logger.error("  FAILED to generate %s: %s", doc_name, exc)

            # Brief pause to avoid hitting rate limits on free-tier Gemini.
            time.sleep(1.5)
            global_idx += 1

    return corpus_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic discharge corpus")
    parser.add_argument("--count", type=int, default=50, help="Target document count (default 50)")
    parser.add_argument(
        "--out",
        default="test-data/synthetic",
        help="Output directory for PDFs and corpus index",
    )
    args = parser.parse_args()

    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    client, model = get_llm_client()
    logger.info("LLM provider: %s | model: %s", provider, model)

    out_dir = Path(args.out)
    corpus_index = generate_corpus(out_dir, provider, client, model)

    # Write corpus index for Neon ingestion (task 1.5 deliverable).
    index_path = out_dir / "corpus_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(corpus_index, f, indent=2)

    logger.info(
        "Done. %d documents generated → %s | Index: %s",
        len(corpus_index), out_dir, index_path,
    )


if __name__ == "__main__":
    main()
