# Tasks 2.2 + 2.3 - Camera Scan, On-Device OCR, Client-to-Server Text Path ✅

**Deliverable:** photograph the paper discharge document, recognize text on
the phone, run the full pipeline - the "hour zero" path that needs no PDF.

**Commits / tag:** `e5de64b` (backend `/analyze/text`), `7a2bf9c` (Flutter
scan screen) / `task-2.2-camera-ocr`

**Design:**
- Scan screen: multi-page capture (camera or library) → Google ML Kit
  latin-script recognition entirely on-device → per-page preview with a
  low-text retake warning → combined text to `POST /analyze/text`.
- **Privacy property:** the photo never leaves the phone. Only recognized
  text crosses the wire - images of paper medical documents stay on-device.
- Backend tags the ingest `ocr_photo` and surfaces a patient-facing
  scan-quality note on the standard warnings channel; text length gates
  reject failed scans with retake guidance instead of burning agent calls.
- Same `_execute_pipeline` lifecycle as the PDF route - progress, timeout,
  and error semantics cannot drift between the two input paths.

**Remaining in 2.2 scope:** document edge detection / perspective correction
(nice-to-have; ML Kit handles moderate skew) - revisit if tester scans show
accuracy problems.

**Demo:** phone camera at a printed synthetic discharge → text preview →
full 7-tab breakdown, with the camera-scan warning banner visible.

**Verified:** flutter analyze clean; debug APK builds with ML Kit natives;
backend path tested live with a corpus document (complete_with_warnings).
