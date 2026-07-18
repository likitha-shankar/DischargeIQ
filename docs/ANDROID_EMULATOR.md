# Running DischargeIQ on the Android Emulator

The Android emulator is the official no-device path for demos, testing, and
recordings. It exists because the iOS simulator CANNOT run the app (Google
ML Kit ships no arm64-simulator slice and Xcode 26 has no Rosetta
simulators). Everything below was verified live on July 18, 2026 - the
Checkpoint-1 backup demo video was recorded this way against the production
backend.

## Prerequisites (already true on the dev Mac)

- Android SDK at `~/Library/Android/sdk` (installed via
  `android-commandlinetools`; see `docs/deliverables/tasks/task-1.10-android-apk.md`)
- An AVD named `pixel8` (`flutter emulators` lists it)
- A release APK (`flutter build apk --release`, or the one in
  `dist/beta-kit/DischargeIQ.apk`). Release builds point at the production
  Cloud Run backend, so the emulator exercises the real system.

## Launch

```bash
export ANDROID_SDK_ROOT=~/Library/Android/sdk ANDROID_HOME=~/Library/Android/sdk
~/Library/Android/sdk/emulator/emulator -avd pixel8 -no-snapshot-load -no-boot-anim &
```

**Gotcha (will bite you):** without `ANDROID_SDK_ROOT` the emulator dies
with `Cannot find AVD system path. Please define ANDROID_SDK_ROOT` - it
guesses `/opt/homebrew` as the SDK root and gives up. Always export first.

Wait for boot (~30-60s):

```bash
adb() { ~/Library/Android/sdk/platform-tools/adb "$@"; }   # adb is not on PATH
adb devices                      # emulator-5554  device  (not "offline")
adb shell getprop sys.boot_completed   # "1" when ready
```

## Install the app and sample documents

```bash
adb install -r dist/beta-kit/DischargeIQ.apk
adb push dist/beta-kit/sample-documents/ /sdcard/Download/
```

Launch from the app drawer, or:

```bash
adb shell am start -n com.likithashankar.dischargeiq/com.example.dischargeiq_mobile.MainActivity
```

## Demo flow on the emulator

The camera-scan path is not meaningful in an emulator (no real camera), so
use the PDF path: **Tap to choose your discharge PDF** opens the system file
picker showing Downloads - pick a sample PDF, then **Upload & Analyze**.
Everything else (progress chips, results tabs, streamed chat, quiz) behaves
exactly as on a phone, against the live backend.

## Recording a demo video

`adb shell screenrecord` caps at 3 minutes per file - record in segments
and concatenate:

```bash
adb shell "screenrecord --time-limit 90 --bit-rate 6000000 /sdcard/seg1.mp4"
# ... drive the app ... repeat per segment, then:
adb pull /sdcard/seg1.mp4 .
printf "file 'seg1.mp4'\nfile 'seg2.mp4'\n" > concat.txt
ffmpeg -f concat -safe 0 -i concat.txt -c copy demo.mp4
```

## Known limits

- Boot from cold takes up to a minute; `-no-snapshot-load` gives a clean
  state (drop the flag for faster warm boots that keep app data).
- No camera, no push-notification sound reliability, no real touch feel -
  final rehearsals still happen on a physical phone.
- The emulator shares the host network: if the app cannot reach prod,
  check the Mac's own connectivity first.
