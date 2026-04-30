import json
from evaluation.run_judge import run_full_evaluation

with open("evaluation/test_cases.json", "r", encoding="utf-8") as f:
    test_cases = json.load(f)

results = run_full_evaluation(test_cases)

with open("evaluation/judge_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("DONE — evaluation complete")