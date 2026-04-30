import anthropic
import json
import os
from dotenv import load_dotenv
from dischargeiq.utils.scorer import fk_check

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def run_judge(agent_output: str, diagnosis: str) -> dict:
    prompt = f"""
You are a clinical evaluator.

Score this output:

Diagnosis: {diagnosis}

Output:
{agent_output}

Return JSON ONLY with:
clinical_accuracy (1-5)
plain_language (1-5)
completeness (1-5)
actionability (1-5)
safety ("pass" or "fail")
"""

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def run_full_evaluation(test_cases):
    results = []

    for case in test_cases:
        print(f"Evaluating {case['id']}...")

        scores = run_judge(case["output"], case["diagnosis"])

        scores["id"] = case["id"]
        scores["diagnosis"] = case["diagnosis"]

        try:
            scores["fk_grade"] = fk_check(case["output"])["fk_grade"]
        except:
            scores["fk_grade"] = None

        results.append(scores)

    return results