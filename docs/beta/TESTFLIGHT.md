# DischargeIQ iOS - TestFlight Setup (Sprint 2, Task 2.4)

Apple developer account: ikitha.shankar@icloud.com (active as of Jul 5, 2026).

What Claude already did (in the repo, reversible):
- Bundle ID: `com.example.dischargeiqMobile` -> `com.likithashankar.dischargeiq`
  (change it before the App Store Connect step below if you want a different one).
- Display name: "Dischargeiq Mobile" -> "DischargeIQ".
- Camera + photo permission strings already present and patient-friendly.
- CocoaPods installed; `flutter build ios --release --no-codesign` verified.

The rest needs your Apple login, so it is on you. Steps in order:

## 1. Register the App ID + create the app record

1. Go to https://appstoreconnect.apple.com -> My Apps -> "+" -> New App.
2. Platform: iOS. Name: DischargeIQ. Primary language: English (U.S.).
3. Bundle ID: pick `com.likithashankar.dischargeiq` from the dropdown. If it is
   not listed, first create it at
   https://developer.apple.com/account/resources/identifiers (App IDs -> "+" ->
   App -> that bundle ID, no special capabilities needed).
4. SKU: any unique string, e.g. `dischargeiq-ios`. Click Create.

## 2. Sign the build in Xcode

```bash
open "dischargeiq_mobile/ios/Runner.xcworkspace"
```

In Xcode:
1. Left panel -> Runner (top) -> TARGETS: Runner -> Signing & Capabilities.
2. Check "Automatically manage signing".
3. Team: select your Apple Developer team (add your Apple ID under
   Xcode -> Settings -> Accounts if it is not listed).
4. Confirm the bundle ID matches `com.likithashankar.dischargeiq`.

## 3. Archive and upload

Easiest path (Xcode GUI):
1. Top bar device selector -> "Any iOS Device (arm64)".
2. Menu: Product -> Archive. Wait for the build.
3. Organizer window opens -> Distribute App -> TestFlight Internal Only (or
   App Store Connect) -> Upload. Let Xcode manage signing.

CLI alternative (if you gave me your Team ID, I wire this up):
```bash
cd dischargeiq_mobile
flutter build ipa --release
# -> build/ios/ipa/*.ipa, then:
xcrun altool --upload-app -f build/ios/ipa/*.ipa -t ios \
  --apiKey <KEY_ID> --apiIssuer <ISSUER_ID>
```
(App Store Connect API key from Users and Access -> Integrations -> App Store
Connect API. Safer than an Apple ID password.)

## 4. Turn on TestFlight testing

1. App Store Connect -> your app -> TestFlight tab.
2. The uploaded build shows "Processing" for a few minutes, then asks for
   export-compliance: DischargeIQ uses only standard HTTPS, so answer
   "No" to custom/non-exempt encryption (uses exempt encryption).
3. Internal Testing -> add testers (up to 100 people on your team, no Apple
   review needed - fastest path for the Gate 2 demo).
4. For external testers (up to 10,000), submit the build for Beta App Review
   first (usually < 24h). Add a "What to test" note and a beta description.

## 5. Testers install

Testers install the TestFlight app from the App Store, then tap your invite
link (email or public link). Point them at `docs/beta/ONBOARDING.md`.

## Gotchas

- First `flutter build ipa` after a machine setup runs a long `pod install`.
- Build number must increment on every upload: bump `version:` in
  `pubspec.yaml` (the `+N` suffix is CFBundleVersion). Currently `1.0.0+1`.
- Export compliance: DischargeIQ = standard HTTPS only. Already handled:
  `ITSAppUsesNonExemptEncryption=false` is set in Info.plist, so no prompt.

## Flag for the later security pass (not a blocker for internal TestFlight)

`ios/Runner/Info.plist` sets `NSAllowsArbitraryLoads=true`, which disables App
Transport Security for all hosts. It exists so debug builds can reach the
laptop LAN backend over plain HTTP. Internal TestFlight (up to 100 testers)
skips Beta App Review, so this does NOT block the Gate 2 demo. But
**external** TestFlight and App Store review can reject a blanket ATS
disable. Before external distribution, scope it: allow arbitrary loads only
for the local dev host, and let release builds (which use HTTPS Cloud Run)
run with ATS on. Tracked with the other security items for the Opus pass.
