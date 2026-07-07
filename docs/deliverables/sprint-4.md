# Sprint 4 - NotebookLM Media and Corpus Lock (Weeks 7–8) ◻

| Task | Deliverable | Status |
|---|---|---|
| 4.1 | Media generation workflow (care plan → NotebookLM audio/video → app) | ◑ scaffolding built early - [task-4.1](tasks/task-4.1.md): per-diagnosis strategy, `/media/{document_type}` endpoint, Streamlit player with text fallback. Remaining: generate the 5 NotebookLM audios |
| 4.2 | Media quality pass (pronunciation, source formatting) | ◻ |
| 4.3 | Spanish support (stretch, cut first if velocity slips) | ◻ |
| 4.4 | Lock the 50-document clinical trial corpus | Corpus generated + in Neon (Sprint 1); version-lock at Week 8 |

Fallback rule (also Sprint 6 task 6.5): media failure always degrades to the
text-only teach-back loop - the comprehension metric is never blocked by media.
