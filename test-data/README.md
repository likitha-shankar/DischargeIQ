# Test Data - Synthetic Discharge Summaries

This folder contains 10 synthetic discharge summary PDFs used for testing Agent 1 (Extraction Agent) in the DischargeIQ pipeline.

## Purpose
These documents simulate real hospital discharge summaries and are used to:
- Validate structured data extraction (Agent 1)
- Test downstream agents (diagnosis explanation, medication rationale, etc.)
- Serve as the evaluation dataset for the full pipeline

## File List

| File Name | Diagnosis | Source Type |
|----------|----------|------------|
| heart_failure_01.pdf | Heart Failure | Synthetic |
| heart_failure_02.pdf | Heart Failure | Synthetic |
| copd_01.pdf | COPD | Synthetic |
| copd_02.pdf | COPD | Synthetic |
| diabetes_01.pdf | Diabetes Management | Synthetic |
| diabetes_02.pdf | Diabetes Management | Synthetic |
| hip_replacement_01.pdf | Hip Replacement | Synthetic |
| hip_replacement_02.pdf | Hip Replacement | Synthetic |
| surgical_01.pdf | Surgical Case (Appendectomy) | Synthetic |
| surgical_02.pdf | Surgical Case (Cholecystectomy) | Synthetic |

## Data Characteristics
Each document includes:
- Patient demographics (fictional)
- Admission and discharge details
- Primary and secondary diagnoses
- Procedures performed
- Medications with dose, frequency, and duration
- Activity and dietary restrictions
- Follow-up appointments
- Red flag symptoms

## Privacy & Compliance
- All documents are fully synthetic.
- No real patient data or PHI is included.
- All names, dates, and identifiers are fictional.

## Notes
- Documents are designed to resemble Epic-style discharge summaries.
- Formatting variations are intentional to test extraction robustness.