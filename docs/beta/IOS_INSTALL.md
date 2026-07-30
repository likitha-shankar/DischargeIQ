# Installing DischargeIQ on iPhone or iPad

Android testers can install the APK in this kit directly. iPhone cannot work
that way: Apple does not allow installing an app from a file you download.
Every iOS install route goes through Apple. There are three, and only the first
is practical for a reviewer.

## 1. TestFlight (the one to use)

You receive an email invite from App Store Connect.

1. Install **TestFlight** from the App Store (free, made by Apple).
2. Open the invite email on the iPhone and tap **View in TestFlight**.
3. Tap **Accept**, then **Install**.
4. Open DischargeIQ from the home screen like any other app.

Builds expire after 90 days. If the app stops opening, ask for a new invite.

**To be invited, send the email address tied to your Apple ID.** That is the
only thing needed, and it must be the Apple ID address specifically, not a
forwarding alias.

## 2. Ad-hoc build (only if a `.ipa` is in this kit)

An ad-hoc build installs only on iPhones whose **UDID** was registered before
the build was made. If `DischargeIQ-ios.ipa` is not in this kit, this route is
not available and there is nothing to try.

If it is present and your device was registered:

1. Connect the iPhone to a Mac.
2. Open **Finder**, select the iPhone in the sidebar.
3. Drag `DischargeIQ-ios.ipa` onto the device window.

If the app installs but refuses to open, the device was not in the provisioning
profile. Send the UDID and ask for a rebuild.

## 3. Build from source

Requires a Mac with Xcode and Flutter, and a free Apple ID. Apps signed with a
free account stop working after **7 days**, so this is for developers only.

```bash
cd dischargeiq_mobile
flutter pub get
flutter run --release        # with the iPhone connected and unlocked
```

## What you need from us

| Route | What to send us | What you need |
|-------|-----------------|---------------|
| TestFlight | Your Apple ID email | The TestFlight app |
| Ad-hoc | Your device UDID | A Mac to install from |
| Source | Nothing | Mac, Xcode, Flutter |

## No account needed inside the app

DischargeIQ has no login. Open it, upload a discharge PDF, and the results
appear. Sample PDFs are in the `sample-documents/` folder of this kit.

**Do not upload a real patient document.** This is a prototype under
evaluation, not an approved clinical system.
