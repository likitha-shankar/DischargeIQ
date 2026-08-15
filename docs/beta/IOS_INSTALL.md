# Installing DischargeIQ on iPhone or iPad

Android testers can install the APK in this kit directly. iPhone cannot work
that way: Apple does not allow installing an app from a file you download.
Every iOS install route goes through Apple.

## Read this first: iPhone testing is limited right now

**There is no TestFlight build, and no invite is coming.** TestFlight requires
a paid Apple Developer account ($99/year), which this project does not have -
see `docs/IOS_ACCESS_FINDINGS.md`. Please do not wait for an email.

If you have an iPhone and want to take part, there are two options:

- **Use an Android phone instead**, if you have access to one. That is the
  supported route and takes two minutes.
- **Hand your iPhone to the developer for ten minutes.** The app can be
  installed over a cable using free provisioning. It then works for **7 days**
  and stops opening, at which point it needs the same ten minutes again.

Everything below documents the routes for completeness. Only the cable route
is available today.

## 1. Direct install over a cable (the one available now)

Needs the developer, a Mac, and your unlocked iPhone in hand.

1. The developer connects the phone and installs the build.
2. On the phone, go to **Settings > General > VPN & Device Management**, tap
   the developer certificate, and tap **Trust**.
3. Open DischargeIQ from the home screen.

The app stops opening after 7 days. That is Apple's limit on free
provisioning, not a bug, and reinstalling does not lose your saved documents.

## 2. TestFlight (not available - needs a paid account)

If LOF provides a shared Apple Developer account, this becomes the practical
route and you would receive an invite from App Store Connect: install
**TestFlight** from the App Store, open the invite on the iPhone, tap
**Accept**, then **Install**. Builds expire after 90 days.

Until that account exists, there is nothing to accept.

## 3. Build from source

Requires a Mac with Xcode and Flutter, and a free Apple ID. Apps signed with a
free account stop working after **7 days**, so this is for developers only.

```bash
cd dischargeiq_mobile
flutter pub get
flutter run --release        # with the iPhone connected and unlocked
```

## What you need from us

| Route | What to send us | What you need | Available? |
|-------|-----------------|---------------|------------|
| Cable install | Your availability | The phone, in person | ✅ yes |
| TestFlight | Your Apple ID email | The TestFlight app | ❌ needs a paid account |
| Source | Nothing | Mac, Xcode, Flutter | ✅ developers only |

## No account needed inside the app

DischargeIQ has no login. Open it, upload a discharge PDF, and the results
appear. Sample PDFs are in the `sample-documents/` folder of this kit.

The first time you open a document, a short notice explains that the summary
is written by AI and is not medical advice. Close it with the X or the OK
button and carry on.

**Do not upload a real patient document.** This is a prototype under
evaluation, not an approved clinical system.
