# DischargeIQ Beta — Tester Onboarding (Sprint 2, Task 2.5)

Thanks for testing DischargeIQ! You'll scan a (fake) hospital discharge
document with your phone camera and get back a plain-language explanation of
the diagnosis, medications, warning signs, and a short "Test yourself" quiz.

## ⚠️ Rule #1 — synthetic documents only

**Never scan or upload a real discharge document — yours or anyone else's.**
The beta backend is not yet cleared for real patient data. Use only the test
documents we give you (they describe fictional patients). If you accidentally
scan something real, tell us immediately so we can purge the session.

Your invite includes 2–3 printed synthetic documents (from the project's
50-document corpus, e.g. a COPD, heart-failure, or hip-replacement case).
Lost them? Ask your contact for replacements — or print any PDF from
`test-data/synthetic/` if you have repo access.

## Install

### Android (available now — direct install)

1. Open the APK link from your invite message on your phone
   (or transfer the `app-release.apk` file we sent you).
2. Tap the file. If Android asks, allow **"Install unknown apps"** for your
   browser/files app (Settings prompt appears automatically — it's a one-time
   switch because this beta build doesn't come from the Play Store yet).
3. Open **DischargeIQ**. No account or login needed. The app talks to our
   hosted backend automatically — any Wi‑Fi or mobile data works.

Play Store internal-testing links replace this direct install later in the
beta (you'll get a new invite; nothing to uninstall).

### iPhone (TestFlight — invites coming shortly)

1. Install **TestFlight** from the App Store.
2. Tap the TestFlight invite link in your invite message.
3. Tap **Install** next to DischargeIQ.

## What to test (15–20 minutes)

Do each of these at least once, on different days if you can:

1. **Camera scan:** Scan → photograph all pages of a printed test document →
   check the text preview → Analyze. Try one scan in bad light on purpose.
2. **Read the results:** all 7 tabs (What Happened, Medications,
   Appointments, Warning Signs, Recovery, Test yourself, AI Review).
   Flag anything confusing, wrong-sounding, or above ~6th-grade reading level.
3. **Take the quiz:** "Test yourself" tab → baseline quiz → learning cards →
   post-quiz. Miss a question on purpose once to see the focused review.
4. **Ask the chat** 2–3 questions about the document (e.g. "when is my
   follow-up?", "can I climb stairs?").

## Reporting problems (and wins)

Message your invite contact or email **lshankar@hawk.illinoistech.edu** with:

- Phone model + OS version (e.g. "Pixel 7, Android 15")
- Which test document you used (e.g. "copd_03")
- What you did, what you expected, what happened
- A screenshot if you have one

Crashes, weird text, slow responses, confusing wording, quiz questions that
feel unfair or leading — all of it is useful. "This worked great" is also a
report; we count active installs and completed quiz loops.

## Known rough edges

- A busy backend can return a **partial** result (some tabs show a fallback
  message). Re-analyzing usually clears it.
- Blurry/dark scans trigger a scan-quality warning — retake the photo.
- The app never diagnoses or changes your treatment. It explains a document.
  (And in this beta, the "patient" is always fictional.)

---

## For the team — building the beta APK

```bash
cd dischargeiq_mobile
flutter build apk --release          # → build/app/outputs/flutter-apk/app-release.apk
```

Release builds default to the hosted Cloud Run backend (`lib/config.dart`);
no `--dart-define` needed for testers. For a laptop-local backend demo use
`flutter run --dart-define=API_BASE=http://<laptop-lan-ip>:8000`.

Monitor during beta: Cloud Run logs (error rates), the clinician dashboard
(`streamlit run ui/clinician_dashboard.py --server.port 8502`) for sessions
and completed quiz loops toward the 10–20 active-install target.
