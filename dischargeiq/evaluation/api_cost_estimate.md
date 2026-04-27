# LLM-as-Judge API Cost Estimate
**Batch evaluation (LLM-as-Judge)**
*Owner: Rushi | Model: claude-sonnet-4-20250514*

---

## 1. Current Pricing (claude-sonnet-4-20250514)

> Source: Anthropic pricing documentation, verified March 2026 via multiple sources
> including Anthropic API docs, The New Stack, and Artificial Analysis.

| Token Type        | Price per 1M Tokens |
|-------------------|---------------------|
| **Input tokens**  | **$3.00**           |
| **Output tokens** | **$15.00**          |

> **Batch API note:** Anthropic's Message Batches API offers a **50% discount**
> on both input and output tokens ($1.50 input / $7.50 output per 1M). If the
> evaluation batch is submitted via the Batch API, costs are halved. Standard
> (real-time) pricing is used as the baseline below.

---

## 2. Token Usage Estimate Per Evaluation Call

Each LLM-as-Judge call consists of:

| Component                         | Estimated Tokens |
|-----------------------------------|-----------------|
| Agent output (discharge explanation) | ~1,500 tokens |
| Judge rubric prompt                  | ~500 tokens   |
| **Total input per call**             | **~2,000 tokens** |
| JSON score response (output)         | ~200 tokens   |

> Sizing rationale:
> - Agent output: discharge summaries typically run 1,000–2,000 tokens; 1,500 is the midpoint.
> - Rubric prompt: the 5-dimension scoring prompt + instructions is ~400–600 tokens.
> - Output: a compact JSON object with 5 fields scores at ~150–250 tokens.

---

## 3. Full Batch Cost Calculation (20 Test Cases)

### Standard API (real-time)

| Metric                        | Calculation                             | Result          |
|-------------------------------|-----------------------------------------|-----------------|
| Total input tokens            | 2,000 tokens × 20 calls                 | **40,000 tokens** |
| Total output tokens           | 200 tokens × 20 calls                   | **4,000 tokens**  |
| Input cost                    | 40,000 ÷ 1,000,000 × $3.00             | **$0.12**         |
| Output cost                   | 4,000 ÷ 1,000,000 × $15.00             | **$0.06**         |
| **Total estimated cost**      |                                         | **$0.18**         |

### Batch API (50% discount)

| Metric               | Calculation                              | Result    |
|----------------------|------------------------------------------|-----------|
| Input cost           | 40,000 ÷ 1,000,000 × $1.50             | $0.06     |
| Output cost          | 4,000 ÷ 1,000,000 × $7.50              | $0.03     |
| **Total batch cost** |                                          | **$0.09** |

---

## 4. Conservative High-End Estimate

Using the upper bound of token estimates (2,500 input + 300 output per call):

| Scenario              | Total Input Tokens | Total Output Tokens | Cost (Standard) | Cost (Batch API) |
|-----------------------|--------------------|---------------------|-----------------|-----------------|
| Midpoint estimate     | 40,000             | 4,000               | $0.18           | $0.09           |
| High-end estimate     | 50,000             | 6,000               | $0.24           | $0.12           |

---

## 5. Agreed Budget Ceiling

| Budget Item                          | Amount  |
|--------------------------------------|---------|
| High-end estimate (standard API)     | $0.24   |
| **Budget ceiling (2× high-end)**     | **$0.50** |
| Recommended pre-load (safety buffer) | **$5.00** |

**Recommendation:** Pre-load or confirm $5.00 of credits are available before
the evaluation batch run. This covers the evaluation batch at standard rates with more
than 20× headroom — enough to re-run the full batch multiple times if needed
during debugging, plus any associated pipeline calls.

> **⚠️ Important:** This estimate covers *only* the LLM-as-Judge evaluation calls.
> It does not include the primary pipeline API calls (generating the discharge
> summaries themselves). Factor those in separately when reviewing total
> API spend for the evaluation period.

---

## 6. Rate Limit Check

- **claude-sonnet-4-20250514 default rate limit:** 50 requests per minute (most tiers)
- **Batch size:** 20 calls
- **Expected throughput:** All 20 calls complete in under 1 minute at standard limits
- **Batch API:** Processes asynchronously — no rate limit concern for batch submission

✅ Rate limits are not a bottleneck for this batch size.

---

## 7. Pre-run checklist

- [ ] Log into [console.anthropic.com](https://console.anthropic.com) and verify credit balance
- [ ] Confirm balance is ≥ $5.00 (or flag to team lead to add credits)
- [ ] Confirm API key in use has Sonnet access (not restricted to Haiku only)
- [ ] Decide: standard real-time API vs. Batch API for evaluation run
- [ ] Review `../prompts/llm_judge_prompt.txt` before the batch evaluation run

---