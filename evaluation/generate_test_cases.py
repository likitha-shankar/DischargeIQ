import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv
from dischargeiq.pipeline.orchestrator import run_pipeline

load_dotenv()

PDFS = [
    ("hf", "heart failure", "test-data/heart_failure_01.pdf"),
    ("hf", "heart failure", "test-data/heart_failure_02.pdf"),
    ("copd", "COPD", "test-data/copd_01.pdf"),
    ("copd", "COPD", "test-data/copd_02.pdf"),
    ("diabetes", "diabetes", "test-data/diabetes_01.pdf"),
    ("diabetes", "diabetes", "test-data/diabetes_02.pdf"),
    ("hip", "hip replacement", "test-data/hip_replacement_01.pdf"),
    ("hip", "hip replacement", "test-data/hip_replacement_02.pdf"),
    ("surgical", "surgical case", "test-data/surgical_case_01.pdf"),
    ("surgical", "surgical case", "test-data/surgical_case_02.pdf"),
]

def combine_output(result):
    data = result.model_dump()

    return f"""
EXTRACTION:
{json.dumps(data.get("extraction", {}), indent=2)}

DIAGNOSIS EXPLANATION:
{data.get("diagnosis_explanation", "")}

MEDICATION RATIONALE:
{data.get("medication_rationale", "")}

RECOVERY TRAJECTORY:
{data.get("recovery_trajectory", "")}

ESCALATION GUIDE:
{data.get("escalation_guide", "")}

PIPELINE STATUS:
{data.get("pipeline_status", "")}
"""

async def main():
    test_cases = []
    counts = {"hf":0,"copd":0,"diabetes":0,"hip":0,"surgical":0}

    for run_number in [1, 2]:
        for prefix, diagnosis, pdf_path in PDFS:
            counts[prefix] += 1
            case_id = f"{prefix}_{counts[prefix]:02d}"

            print(f"Running {case_id}...")

            result = await run_pipeline(pdf_path)

            test_cases.append({
                "id": case_id,
                "diagnosis": diagnosis,
                "output": combine_output(result)
            })

    Path("evaluation").mkdir(exist_ok=True)

    with open("evaluation/test_cases.json", "w", encoding="utf-8") as f:
        json.dump(test_cases, f, indent=2)

    print("\nDONE — 20 test cases created")

if __name__ == "__main__":
    asyncio.run(main())