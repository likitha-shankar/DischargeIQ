# DischargeIQ - iOS Access Findings

**Author:** Likitha Shankar
**Date:** 1 August 2026
**For:** Leap of Faith, LLC (John Trzesniak, Tanuj Pravin)
**Fulfills:** Work Plan v2, task 2.5 (iOS access findings, reported before any spend)

---

## The one page

The research-before-spend ladder was worked from the bottom up. **Rung (b),
free 7-day development provisioning, is proven on a real iPhone** - the app
builds, signs, installs, and runs the full flow against the live Cloud Run
backend. No money has been requested and none is needed to keep demoing on
iOS.

That covers demos. It does **not** cover testers. Without a paid Apple
Developer Program membership there is no TestFlight, and without TestFlight
an iPhone tester cannot install the app themselves - the device has to be
physically provisioned by me and reconnected every seven days. **The
Checkpoint 2 tester cohort therefore has to be Android**, unless LOF can
provide rung (a).

**Rung (a) - an LOF shared Apple Developer account - has not been asked for
yet.** That is the open item, and it is the only one that changes the answer.
Steve and Chandan run similar deployments for the Thera product, so the
account may already exist. It costs nothing to ask, and it would convert iOS
from "demo only" to "testers can install it".

**Recommendation:** ask Steve and Chandan whether an existing LOF Apple
Developer account can add this app before considering the $99. If the answer
is no and iOS testers matter for Checkpoint 3, that is the point to revisit
spending. If iOS testers do not matter, rung (b) is sufficient for the whole
engagement.

---

## Rung (b): free 7-day development provisioning - PROVEN

Verified repeatedly on a physical iPhone 14 Pro between 18 and 31 July 2026.

| What was tested | Result |
|---|---|
| Build and sign with a free Apple ID | Works. Signing identity `Apple Development: likitha.shankar@icloud.com`, team `4ZARFDN3RD` |
| Install to a physical device | Works, over USB via `xcrun devicectl device install app` |
| Run the full flow | Works - upload, six-agent pipeline, results tabs, grounded chat, teach-back quiz, against the live Cloud Run backend |
| Expiry | **Measured, not assumed.** The current profile carries `ExpirationDate 2026-08-06T16:15:53Z`, exactly seven days from generation |

### The expiry is real, and it was observed the hard way

The app was installed on 18 July. By 30 July the phone reported **"DischargeIQ
is no longer available"** and refused to launch. Investigation found the
signing certificate still valid but **zero provisioning profiles on disk** -
they had expired and been purged. Nothing was wrong with the build.

Recovery required one interactive step that cannot be scripted: signing back
into the Apple ID in Xcode (Settings → Accounts), because Xcode had been
signed out and could not request a fresh profile. After that, `xcodebuild
-allowProvisioningUpdates` regenerated the profile automatically and the app
was rebuilt and reinstalled in about two minutes.

### Operating cost of staying on rung (b)

- **Every 7 days**, per device: rebuild and reinstall over USB. ~2 minutes.
- The device must be physically present. There is no remote path.
- The Apple ID must stay signed into Xcode, or the refresh needs a manual
  sign-in with 2FA first.
- **Demo-day risk:** the profile in hand expires **6 August**. Any checkpoint
  demo on iOS needs a rebuild within the seven days before it. For the
  Checkpoint 2 demo on **18 August**, that means rebuilding on or after
  11 August. This is now on the demo checklist.

## Rung (a): LOF shared Apple Developer account - NOT YET ASKED

This is the gap in the ladder. The plan names Steve and Chandan as running
similar deployments for the Thera product, which suggests an organisation
account may already exist and could add one more app at no marginal cost.

What it would unlock that rung (b) cannot:

- **TestFlight.** Testers install the app themselves from an email invite. No
  physical device handover, no weekly reconnection.
- **90-day builds** instead of 7-day, so the app does not die between
  checkpoints.
- **Up to 100 external testers**, which is well beyond the 10-15 this
  engagement needs.

What is needed from LOF to evaluate it: whether an Apple Developer Program
membership exists under a Leap of Faith organisation, and whether an
additional bundle identifier (`com.likithashankar.dischargeiq`, or an
LOF-namespaced equivalent) can be added to it. If yes, the practical steps are
an App Store Connect user invitation and a change of `DEVELOPMENT_TEAM` in the
Xcode project - a one-line change on this side.

## Rung (c): $99 individual enrollment - NOT REQUESTED

LOF indicated it could likely cover this once alternatives were checked. The
alternatives have now been checked, and this report exists so that the request
is not made before rung (a) has an answer.

Two things worth stating plainly:

- The developer is a student and is not funding this personally. If iOS
  distribution to testers becomes a requirement and rung (a) is unavailable,
  the $99 becomes the only remaining route.
- Enrollment is not instant. Individual enrollment usually clears in a day or
  two but can take longer with identity verification, so it is not something
  to start in the week of a checkpoint.

## What this means for the plan

| Item | Effect |
|---|---|
| Checkpoint 2 demo (18 Aug) | Unaffected. iOS demos run on rung (b); rebuild on or after 11 Aug |
| Checkpoint 2 testers | **Android only.** The beta kit ships a universal APK that installs directly. `docs/beta/IOS_INSTALL.md` explains the iOS position honestly to any tester who asks |
| "10-20 active installs" target | Reachable on Android. State the iOS limitation at the checkpoint rather than letting it read as a missed target |
| Checkpoint 4 production builds | Store-signed builds are out of scope without a paid account. "Production build" here means the release APK plus a release iOS build installed via development provisioning |

## Current state of the app on iOS

Working and installed on a physical device as of 31 July 2026, running the
complete patient flow against the hosted backend. The constraint is
distribution, not the build.
