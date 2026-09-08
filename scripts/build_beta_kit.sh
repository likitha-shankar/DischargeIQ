#!/usr/bin/env bash
#
# scripts/build_beta_kit.sh
#
# Assemble the DischargeIQ tester kit into one shareable folder + zip.
# Owner: Likitha Shankar.
#
# Bundles the Android APK, the iOS install instructions, the onboarding guide,
# and three synthetic discharge PDFs so a reviewer has everything needed to
# install and run the app without repo access.
#
# ANDROID vs iOS - they are not symmetric, and the kit is honest about it:
#   Android: the APK in this kit installs directly. Nothing else needed.
#   iOS:     Apple does not permit installing an app from a file the way
#            Android does, and there is NO TestFlight build - that needs a
#            paid Apple account this project does not have. An iPhone tester
#            must hand the device to the developer for a cable install that
#            lasts 7 days. The kit therefore carries instructions, not an
#            installable iOS binary. An .ipa is included ONLY if one has been
#            built, and even then it installs only on pre-registered UDIDs.
#
# The release build already points at the hosted Cloud Run backend (see
# dischargeiq_mobile/lib/config.dart), so it works on any network with no
# local server.
#
# Output (dist/ is gitignored - build artifacts, not source):
#   dist/beta_kit/                 the folder to share
#   dist/DischargeIQ-beta-kit.zip
#
# Usage:
#   cd dischargeiq_mobile && flutter build apk --release   # if the APK is stale
#   bash scripts/build_beta_kit.sh

set -euo pipefail
cd "$(dirname "$0")/.."

KIT="dist/beta_kit"
SAMPLES=(heart_failure_01 copd_01 hip_replacement_01)

# ── build the APK here, with the key compiled in ────────────────────────────
#
# This used to say "build it first" and point at a bare `flutter build apk
# --release`. That command produces an APK that 401s on EVERY analysis: the
# hosted backend has required a bearer key since 15 Aug 2026, and the beta
# docs telling testers no --dart-define was needed were written on 14 Aug, one
# day before. A tester following them gets an app that looks completely broken
# while the backend is perfectly healthy - the same failure deploy_ios.sh
# already guards against for iOS.
#
# So the kit builds its own APK and refuses to assemble without the key,
# rather than silently packaging whatever stale artifact is on disk.
API_KEY=$(grep -E '^DISCHARGEIQ_API_KEY=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d "\"' \r")
if [[ -z "${API_KEY:-}" ]]; then
  echo "DISCHARGEIQ_API_KEY not found in .env." >&2
  echo "Without it every analysis in the shipped APK returns 401 and the app" >&2
  echo "looks broken to the tester. Add the key, then re-run." >&2
  exit 1
fi

if [[ "${SKIP_APK_BUILD:-}" != "1" ]]; then
  echo "==> Building the release APK (key compiled in)"
  (cd dischargeiq_mobile && flutter build apk --release \
     --dart-define=API_KEY="$API_KEY")
fi

# Prefer the arm64 split APK when it exists (smaller), else the universal one.
# The universal build is the safer default to hand a stranger: it runs on every
# ABI, so a reviewer with an older or x86 device is not silently blocked.
APK_SPLIT="dischargeiq_mobile/build/app/outputs/flutter-apk/app-arm64-v8a-release.apk"
APK_UNIVERSAL="dischargeiq_mobile/build/app/outputs/flutter-apk/app-release.apk"

if [ -f "$APK_UNIVERSAL" ]; then
  APK="$APK_UNIVERSAL"
  APK_NOTE="universal (runs on all Android devices)"
elif [ -f "$APK_SPLIT" ]; then
  APK="$APK_SPLIT"
  APK_NOTE="arm64 only (most modern phones; not x86 emulators)"
else
  echo "ERROR: no release APK found."
  echo "Build it first: (cd dischargeiq_mobile && flutter build apk --release)"
  exit 1
fi

rm -rf "$KIT"
mkdir -p "$KIT/sample-documents"

cp "$APK" "$KIT/DischargeIQ-android.apk"
cp docs/beta/ONBOARDING.md "$KIT/READ-ME-FIRST.md"
cp docs/beta/IOS_INSTALL.md "$KIT/iOS-INSTALL.md"

# Include an ad-hoc .ipa only if one was actually exported. Absent is the
# normal case - see the iOS note in the header.
IPA=$(find dischargeiq_mobile/build/ios/ipa -name '*.ipa' 2>/dev/null | head -1 || true)
if [ -n "$IPA" ]; then
  cp "$IPA" "$KIT/DischargeIQ-ios.ipa"
  IPA_LINE="  DischargeIQ-ios.ipa    - ad-hoc build; installs ONLY on pre-registered devices"
else
  IPA_LINE="  (no iOS binary - iPhone needs a 7-day cable install, see iOS-INSTALL.md)"
fi

# Three synthetic documents, one per common diagnosis. Synthetic only -
# never ship a real discharge document (repo hard rule 6). These live at the
# top of test-data/; the generated corpus that used to hold copies was
# removed, so do not reintroduce a test-data/synthetic/ path here.
for name in "${SAMPLES[@]}"; do
  src="test-data/${name}.pdf"
  if [ -f "$src" ]; then
    cp "$src" "$KIT/sample-documents/${name}.pdf"
  else
    echo "WARN: $src missing, skipped"
  fi
done

{
  echo "DischargeIQ Tester Kit"
  echo "Built: $(date '+%Y-%m-%d %H:%M')"
  echo "Backend: hosted Cloud Run (no local server needed)"
  echo ""
  echo "Contents:"
  echo "  DischargeIQ-android.apk - install this on Android; $APK_NOTE"
  echo "$IPA_LINE"
  echo "  READ-ME-FIRST.md        - setup + what to test"
  echo "  iOS-INSTALL.md          - how iPhone testers get the app"
  echo "  sample-documents/       - synthetic discharge PDFs to try (NOT real patients)"
  echo ""
  echo "No real patient data is included in this kit."
} > "$KIT/MANIFEST.txt"

ZIP="dist/DischargeIQ-beta-kit.zip"
rm -f "$ZIP"
(cd dist && zip -rq "$(basename "$ZIP")" beta_kit)

echo "Kit ready:"
echo "  Folder: $KIT"
echo "  Zip:    $ZIP  ($(du -h "$ZIP" | cut -f1))"
if [ -z "$IPA" ]; then
  echo
  echo "NOTE: Android installs from this zip directly."
  echo "      iPhone has no TestFlight build - 7-day cable install only, see docs/beta/IOS_INSTALL.md."
fi

# The app has no local fallback: every upload goes to the hosted backend. If
# that backend is down, a reviewer installs the kit and sees only errors, and
# the failure looks like a broken app rather than a stopped service. Check
# before the zip gets sent, not after.
HEALTH_URL="$(grep -o "https://[^']*run\.app/api" dischargeiq_mobile/lib/config.dart | head -1)/health"
STATUS=$(curl -s -o /dev/null -w '%{http_code}' --max-time 60 "$HEALTH_URL" || echo "000")
echo
if [ "$STATUS" = "200" ]; then
  echo "Backend check: OK ($HEALTH_URL)"
else
  echo "*** DO NOT SHARE THIS KIT YET ***"
  echo "Backend check FAILED: HTTP $STATUS at $HEALTH_URL"
  echo "The app cannot analyze anything until that service answers 200."
  echo "Redeploy Cloud Run (and confirm billing is active), then rebuild."
fi
