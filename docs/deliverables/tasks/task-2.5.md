# Task 2.5 - Android Beta Distribution (direct-install APK) ✅

**Deliverable:** installable release APKs so beta testers on Android can run
DischargeIQ without waiting on store accounts (decision: direct install while
Apple/Play accounts are pending; Play deferred to first LOF payout).

**Commit / tag:** pending review - suggested tag `task-2.5-android-apk`

**What was blocked and how it was unblocked:**
- Android SDK was not installed on the dev Mac. Installed via
  `brew install --cask android-commandlinetools` + `sdkmanager`
  (platform-tools, platforms;android-35, build-tools;35.0.0) into
  `~/Library/Android/sdk`; `flutter config --android-sdk` pointed at it and
  licenses accepted. Java 17 was already present.
- First release build failed in R8: the ML Kit plugin references the
  Chinese/Devanagari/Japanese/Korean recognizer option classes but the app
  bundles ONLY the Latin recognizer (English discharge documents). Fix:
  `android/app/proguard-rules.pro` with `-dontwarn` for the four script
  packs, wired via `proguardFiles` in `build.gradle.kts`.

**Config changes (`dischargeiq_mobile/android/app/build.gradle.kts`):**
- `applicationId` -> `com.likithashankar.dischargeiq` (matches the iOS bundle
  id from Task 2.4). `namespace` intentionally stays
  `com.example.dischargeiq_mobile` - it is the code package.
- Release build signs with the debug key ON PURPOSE for the direct-install
  beta path; Play upload later needs a real keystore.

**Artifacts (`dischargeiq_mobile/build/app/outputs/flutter-apk/`):**
| APK | Size | Who installs it |
|---|---|---|
| `app-arm64-v8a-release.apk` | 30.9MB | Every modern Android phone - SEND THIS ONE |
| `app-armeabi-v7a-release.apk` | 24.1MB | Old 32-bit devices only |
| `app-release.apk` (universal) | 82.1MB | Fallback when the tester's ABI is unknown |

Build: `flutter build apk --release --split-per-abi`

**Tester flow:** covered in [ONBOARDING.md](../../beta/ONBOARDING.md) -
share the arm64 APK (Drive/AirDrop), tester enables "install unknown apps",
opens the file, done.

**Verified:** clean `assembleRelease` (45.7s after Gradle warm-up), all three
split APKs + universal produced with the ML Kit proguard fix.
