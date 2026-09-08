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
# Must match backup_ios_data.sh. Empty here would make the install check
# report "absent" for every state, which is the direction that loses data.
BUNDLE_ID="com.likithashankar.dischargeiq"

cd "$(dirname "$0")/.."

# Back up BEFORE touching the device. Even an in-place upgrade can go wrong,
# and the container is the only copy of the document library, the PDFs, the
# profiles, and all gamification progress - none of it exists server-side.
# Is the app actually on the phone? Three states, and they must not be
# confused - the backup guard treats "cannot read the container" as a reason
# to abort, which is right when the device is silent and wrong when the app
# is simply gone. On 8 Sep 2026 the app was uninstalled, the guard aborted a
# legitimate reinstall, and the fix was to run the build and install steps by
# hand. Working around a data-safety guard is not a thing to do twice.
#
# Echoes: installed | absent | unreachable
#
# Distinguished by CONTENT, not exit code alone:
#   installed   - rc 0 and the bundle id appears
#   absent      - rc 0 and it does not (devicectl prints an empty app list)
#   unreachable - rc non-zero, or the device could not be located
_app_state() {
  local out rc attempt
  # Retried: the wireless link drops, and a single failed probe must not be
  # read as "the device is gone" when the next one would have answered.
  for ((attempt = 1; attempt <= 3; attempt++)); do
    rc=0
    out=$(xcrun devicectl device info apps \
      --device "$DEVICE_UDID" --bundle-id "$BUNDLE_ID" 2>&1) || rc=$?
    if [[ "$rc" -eq 0 ]]; then
      if [[ "$out" == *"$BUNDLE_ID"* ]]; then echo "installed"; else echo "absent"; fi
      return 0
    fi
    sleep 3
  done
  echo "unreachable"
}

echo "==> Checking whether the app is installed"
APP_STATE=$(_app_state)
case "$APP_STATE" in
  installed)
    echo "    installed - backing up before touching it"
    ./scripts/backup_ios_data.sh backup "$DEVICE_UDID"
    ;;
  absent)
    # Nothing on the device to lose, so there is nothing to back up. This is
    # the clean-reinstall path and it is allowed to proceed.
    echo "    NOT installed - clean reinstall, nothing to back up"
    echo "    Restore previous data afterwards with:"
    echo "      ./scripts/backup_ios_data.sh restore device-backups/<newest>"
    ;;
  *)
    # The device did not answer. Installing now could land on live data with
    # no copy of it, which is exactly how the container was lost on 4 Aug.
    echo "Cannot reach the device after 3 attempts." >&2
    echo "This is NOT the same as the app being absent - the phone did not" >&2
    echo "answer, so it cannot be established whether there is data at risk." >&2
    echo "Reconnect and retry rather than installing blind." >&2
    exit 1
    ;;
esac

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
