# Quiz Gap Report - prompt-tuning evidence (Task 3.4)

Generated: 2026-07-18 17:28 UTC
Completed pre→post loops: **2** (minimum for tuning decisions: 10)

> ⚠️ **LOW CONFIDENCE** - below the minimum sample. This run shows the
> pipeline works; do NOT edit prompts from it. Re-run once Sprint 2
> beta testers produce real loops.

## Miss rate per domain

| Domain | Baseline | After teaching | Owning prompt |
|---|---|---|---|
| Activity & diet | 50% | 0% | `prompts/agent4_system_prompt.txt (Recovery)` |
| Follow-up visits | 50% | 0% | `prompts/agent1_system_prompt.txt (extraction) + appointments tab` |
| Medications | 25% | 0% | `prompts/agent3_system_prompt.txt (Medications)` |
| Warning signs | 75% | 0% | `prompts/agent5_system_prompt.txt (Warning Signs - safety-critical)` |
| What happened | 0% | 0% | `prompts/agent2_system_prompt.txt (What Happened)` |

## Tuning targets

_None emitted - sample below minimum._

## Post-teaching failures by diagnosis

_No post-teaching failures recorded._
