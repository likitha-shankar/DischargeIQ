# DischargeIQ Beta - Tester Onboarding (Sprint 2, Task 2.5)

Thanks for testing DischargeIQ! You'll scan a (fake) hospital discharge
document with your phone camera and get back a plain-language explanation of
the diagnosis, medications, warning signs, and a short "Test yourself" quiz.

## ⚠️ Rule #1 - synthetic documents only

**Never scan or upload a real discharge document - yours or anyone else's.**
The beta backend is not yet cleared for real patient data. Use only the test
documents we give you (they describe fictional patients). If you accidentally
scan something real, tell us immediately so we can purge the session.

Your invite includes 2–3 printed synthetic documents (from the project's
50-document corpus, e.g. a COPD, heart-failure, or hip-replacement case).
Lost them? Ask your contact for replacements - or print any PDF from
`test-data/synthetic/` if you have repo access.

## Install

### Android (available now - direct install)

1. Open the APK link from your invite message on your phone
   (or transfer the `app-release.apk` file we sent you).
2. Tap the file. If Android asks, allow **"Install unknown apps"** for your
   browser/files app (Settings prompt appears automatically - it's a one-time
   switch because this beta build doesn't come from the Play Store yet).
3. Open **DischargeIQ**. No account or login needed. The app talks to our
   hosted backend automatically - any Wi‑Fi or mobile data works.

Play Store internal-testing links would replace this direct install later,
but there is no Play Console account this summer either, so the APK in this
kit stays the distribution route for the whole beta.

### iPhone (no invite is coming - please read)

There is **no TestFlight build**. It needs a paid Apple Developer account,
which this project does not have. Do not wait for an invite email.

1. Use an **Android phone** if you can get hold of one. That is the supported
   route and takes two minutes.
2. Otherwise, hand your iPhone to the developer for ten minutes and it can be
   installed over a cable. The app then works for **7 days** before it needs
   the same ten minutes again.

Details: `iOS-INSTALL.md` in this kit.

## What to test (15–20 minutes)

Do each of these at least once, on different days if you can:

1. **Camera scan:** Scan → photograph all pages of a printed test document →
   check the text preview → Analyze. Try one scan in bad light on purpose.
2. **Read the results:** all 7 tabs (What happened, Medications,
   Appointments, Warning signs, Recovery, Test yourself, Discharge Check).
   Flag anything confusing, wrong-sounding, or above ~6th-grade reading level.
   A usage disclaimer appears the first time you open a new document; it
   closes with the X or the OK button.
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
feel unfair or leading - all of it is useful. "This worked great" is also a
report; we count active installs and completed quiz loops.

## Known rough edges

- A busy backend can return a **partial** result (some tabs show a fallback
  message). Re-analyzing usually clears it.
- Blurry/dark scans trigger a scan-quality warning - retake the photo.
- The app never diagnoses or changes your treatment. It explains a document.
  (And in this beta, the "patient" is always fictional.)

---

## For the team - building the beta APK

```bash
bash scripts/build_beta_kit.sh       # builds the APK and assembles the kit
```

Use the script rather than a bare `flutter build apk --release`. Release
builds point at the hosted Cloud Run backend (`lib/config.dart`), and that
backend has required a bearer key since 15 Aug 2026 - an APK built without
`--dart-define=API_KEY` returns **401 on every analysis**, so the app looks
broken to the tester while the backend is perfectly healthy. The script
compiles the key in from `.env` and refuses to build without it.

(This page said "no `--dart-define` needed for testers" until 8 Sep 2026. It
was written on 14 August, the day before the key gate landed.)

For a laptop-local backend demo use
`flutter run --dart-define=API_BASE=http://<laptop-lan-ip>:8000`.

Monitor during beta: Cloud Run logs (error rates), the clinician dashboard
(`streamlit run ui/clinician_dashboard.py --server.port 8502`) for sessions
and completed quiz loops toward the 10–20 active-install target.
