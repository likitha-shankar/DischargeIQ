# Task 2.5 - iOS Access Research, Before Any Spend ✅

**Deliverable:** the research-before-spend ladder from Work Plan v2,
evaluated hands-on, with findings reported before any money is requested.

**For:** John and Tanuj (Leap of Faith, LLC)
**Date:** July 18, 2026
**Researched by:** Likitha Shankar

## The ladder, evaluated

**(a) LOF shared Apple Developer account or Mac build support.**
Open thread: John and Tanuj to consult Steve and Chandan, who run similar
deployments for the Thera product. This remains the preferred no-new-cost
option if an organization seat exists. Status: awaiting their answer;
nothing currently blocks on it (see b).

**(b) Free 7-day development provisioning on a personal device. PROVEN.**
This is how every iOS demo has run since July 11. Facts from daily use:

- `flutter build ios --release` then
  `xcrun devicectl device install app --device <device-id> build/ios/iphoneos/Runner.app`
  installs on the developer's iPhone with a free Apple ID. No cost.
- The signature expires every 7 days; a one-command rebuild + reinstall
  refreshes it. Workable for demos, unusable for distributing to testers.
- Hard limitation discovered along the way: the iOS SIMULATOR cannot run
  the app at all. Google ML Kit ships fat frameworks with no
  arm64-simulator slice, and Xcode 26 removed Rosetta simulators, so
  there is no no-device iOS path. The no-device demo path is the ANDROID
  EMULATOR (documented in `docs/ANDROID_EMULATOR.md`; it produced the
  recorded Checkpoint-1 backup demo on July 18).
- TestFlight is NOT available on the free tier. iOS tester distribution
  requires (a) or (c).

**(c) The $99/year individual Apple Developer enrollment.**
Unlocks TestFlight (iOS tester distribution) and App Store production
builds (task 4.5). LOF indicated it can likely cover this once
alternatives are checked - this report is that check.

## Findings and recommendation

1. **No spend is needed for the current phase.** Demos run on a real
   iPhone via free provisioning; testers are covered by the Android
   direct-install beta kit; anyone without a device uses the Android
   emulator. Sprint-1 and Sprint-2 commitments are deliverable at $0.
2. **The $99 becomes necessary exactly when iOS testers or store builds
   do** - Sprint 4 (task 4.5), or earlier only if LOF wants
   iPhone-owning beta testers on TestFlight.
3. **Ask (a) first:** if Steve and Chandan's setup includes an Apple
   Developer organization with a spare seat, TestFlight comes at no new
   cost. Otherwise request the $99 at the Sprint-4 boundary, not now.

**Money requested today: none.**
