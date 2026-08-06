#!/usr/bin/env bash
#
# Build DischargeIQ for the iPhone and install it.
#
# Exists because of one signing gap: Flutter's native-assets pipeline emits
# objective_c.framework ad-hoc signed (no team identifier), and iOS refuses to
# install a bundle containing an ad-hoc signed framework:
#
#   Failed to verify code signature of .../objective_c.framework
#   0xe8008014 (The executable contains an invalid signature.)
#
# Every other framework in the app is signed correctly by Xcode; only this one
# is missed, so every `flutter build ios` needs the same repair. Re-signing the
# framework and then re-sealing the app bundle (the outer signature covers the
# frameworks, so the order matters) makes the install succeed.
#
# Usage:  ./scripts/deploy_ios.sh [device-udid]
#
# DO NOT deploy with `flutter install`. It uninstalls the old build first, and
# an iOS uninstall deletes the app container - the on-device document library,
# the saved PDFs, every profile, and all gamification progress go with it
# (lost exactly this way on Aug 4, 2026). `devicectl device install app`, used
# below, upgrades in place and keeps the container.
#
# After a fresh install iOS may ask to trust the developer certificate:
#   Settings > General > VPN & Device Management > Apple Development: ... > Trust
# Free provisioning profiles last 7 days; past that, rebuild to re-provision.

set -euo pipefail

DEVICE_UDID="${1:-00008120-001A3D281A78C01E}"
APP_DIR="dischargeiq_mobile"
APP="$APP_DIR/build/ios/iphoneos/Runner.app"

cd "$(dirname "$0")/.."

# Back up BEFORE touching the device. Even an in-place upgrade can go wrong,
# and the container is the only copy of the document library, the PDFs, the
# profiles, and all gamification progress - none of it exists server-side.
echo "==> Backing up on-device data"
./scripts/backup_ios_data.sh backup "$DEVICE_UDID"

# A release build talks to Cloud Run, which requires the bearer key - without
# it every analysis comes back 401 and the app looks broken while the backend
# is perfectly healthy. The key is a spend gate, not a patient secret, but it
# must be compiled in at build time.
API_KEY=$(grep -E '^DISCHARGEIQ_API_KEY=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"' \r')
if [[ -z "${API_KEY:-}" ]]; then
  echo "DISCHARGEIQ_API_KEY not found in .env - the release build would 401" >&2
  echo "on every analysis against Cloud Run. Add it, then re-run." >&2
  exit 1
fi

echo "==> Building iOS release (API key compiled in)"
(cd "$APP_DIR" && flutter build ios --release --dart-define=API_KEY="$API_KEY")

# The signing identity is whatever this Mac has for the team in the Xcode
# project. Taking the first codesigning identity keeps the script working
# after a certificate renewal without editing a hardcoded hash.
IDENTITY=$(security find-identity -v -p codesigning | awk 'NR==1 {print $2}')
if [[ -z "$IDENTITY" ]]; then
  echo "No codesigning identity found. Open Xcode and sign in first." >&2
  exit 1
fi
echo "==> Signing identity: $IDENTITY"

# Preserve the entitlements Xcode produced rather than inventing a set; they
# carry the application-identifier the provisioning profile is matched against.
ENTITLEMENTS=$(mktemp -t dischargeiq_ent).plist
codesign -d --entitlements - --xml "$APP" 2>/dev/null > "$ENTITLEMENTS"
trap 'rm -f "$ENTITLEMENTS"' EXIT

# Re-sign any ad-hoc framework, not just objective_c by name: the native-assets
# pipeline can add more of them as FFI packages are pulled in, and a name-based
# fix would silently stop covering the problem.
resigned=0
for framework in "$APP"/Frameworks/*.framework; do
  # Capture first, then match. Piping into `grep -q` under `set -o pipefail`
  # silently inverts this test: grep exits on the first match, codesign dies of
  # SIGPIPE, and pipefail reports the pipeline as failed - so a framework that
  # IS ad-hoc looks fine and never gets re-signed.
  info=$(codesign -dv "$framework" 2>&1 || true)
  if [[ "$info" == *"flags=0x2(adhoc)"* ]]; then
    echo "==> Re-signing ad-hoc framework: $(basename "$framework")"
    codesign --force --sign "$IDENTITY" --timestamp=none "$framework"
    resigned=$((resigned + 1))
  fi
done
echo "==> Re-signed $resigned ad-hoc framework(s)"

echo "==> Re-sealing the app bundle"
codesign --force --sign "$IDENTITY" --entitlements "$ENTITLEMENTS" \
  --timestamp=none "$APP"
codesign --verify --deep --strict "$APP"

echo "==> Installing on $DEVICE_UDID"
# The wireless link drops intermittently (CoreDeviceError 4000), so retry
# rather than fail the whole deploy on a transient disconnect.
installed=0
for attempt in 1 2 3; do
  if xcrun devicectl device install app --device "$DEVICE_UDID" "$APP"; then
    installed=1
    break
  fi
  echo "    install attempt $attempt failed; retrying" >&2
  sleep 5
done

if [[ "$installed" -ne 1 ]]; then
  echo "INSTALL FAILED - the app on the phone is unchanged." >&2
  exit 1
fi

echo
echo "Installed. If the app will not open, trust the certificate on the phone:"
echo "  Settings > General > VPN & Device Management > Apple Development > Trust"
