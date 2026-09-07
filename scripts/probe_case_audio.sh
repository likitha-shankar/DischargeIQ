#!/usr/bin/env bash
#
# scripts/probe_case_audio.sh
#
# Prove the per-case audio explainer actually PLAYS on the iPhone.
#
# The widget tests run on a fake canvas with no audio hardware, so they can
# show that a tap requests the right bytes but not that iOS decodes them and
# runs its audio clock. This drives the real plugin on the real device against
# the live backend.
#
# REQUIRES A USB CABLE. Integration tests need the VM service port, and a
# wirelessly paired iPhone does not carry it - the run fails immediately with
# "Cannot start app on wirelessly tethered iOS device". `flutter test` has no
# --publish-port flag, so a cable is the fix rather than an argument.
#
# Usage:  ./scripts/probe_case_audio.sh [device-udid]
#
# Safe for on-device data: this installs a debug build over the app, which is
# an in-place upgrade, and it backs the container up first regardless. It does
# NOT uninstall (an iOS uninstall deletes the container - the document
# library, saved PDFs, profiles and all progress).
#
# Afterwards the phone is left carrying the DEBUG build. Run
# ./scripts/deploy_ios.sh to put the release build back.

set -euo pipefail

DEVICE_UDID="${1:-00008120-001A3D281A78C01E}"
CLOUD_RUN="https://dischargeiq-678599658918.us-central1.run.app/api"

cd "$(dirname "$0")/.."

# ---------------------------------------------------------------- key ------
# The endpoint is the only auth-gated one in the app, so a build without the
# key returns 401 and the probe fails for a reason that has nothing to do
# with audio. Fail loudly here instead.
API_KEY=$(grep -E '^DISCHARGEIQ_API_KEY=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d "\"' \r")
if [[ -z "${API_KEY:-}" ]]; then
  echo "DISCHARGEIQ_API_KEY not found in .env - the probe would 401" >&2
  exit 1
fi

# ------------------------------------------------------------- cable ------
echo "==> Checking the device is on a cable"
# Captured ONCE. Wireless devices appear only after a scan that takes several
# seconds, so two separate calls race it and the second can miss the phone
# entirely - which reads as "not connected" when it is merely still scanning.
DEVICES=$(flutter devices --device-timeout 15 2>/dev/null || true)
DEVICE_LINE=$(printf '%s\n' "$DEVICES" | grep "$DEVICE_UDID" || true)

if [[ -z "$DEVICE_LINE" ]]; then
  echo "Device $DEVICE_UDID not found. Is it plugged in and unlocked?" >&2
  exit 1
fi
if printf '%s\n' "$DEVICE_LINE" | grep -qi "wireless"; then
  echo >&2
  echo "The iPhone is paired WIRELESSLY. Integration tests cannot start an" >&2
  echo "app over a wireless pairing - they need the VM service port." >&2
  echo >&2
  echo "  1. Connect the iPhone to this Mac with a USB cable" >&2
  echo "  2. Unlock the phone and tap Trust if asked" >&2
  echo "  3. In Xcode > Window > Devices and Simulators, UNTICK" >&2
  echo "     'Connect via network' for this device" >&2
  echo "  4. Re-run this script" >&2
  exit 1
fi

# ------------------------------------------------------------ backup ------
# Same rule as deploy_ios.sh: back up before touching the device. None of the
# on-device data exists server-side.
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="device-backups/${STAMP}"
echo "==> Backing up on-device data to ${DEST}"
mkdir -p "$DEST"
xcrun devicectl device copy from --device "$DEVICE_UDID" \
  --domain-type appDataContainer \
  --domain-identifier com.likithashankar.dischargeiq \
  --source Documents --destination "$DEST/Documents" 2>/dev/null || \
  echo "    (no Documents to back up yet)"

# ------------------------------------------------------------- probe ------
echo "==> Running the on-device audio probe (2-4 minutes)"
echo "    Generation is a live LLM + TTS call, so the first assertion waits."
cd dischargeiq_mobile
flutter test integration_test/case_audio_probe_test.dart \
  -d "$DEVICE_UDID" \
  --dart-define=API_KEY="$API_KEY" \
  --dart-define=API_BASE="$CLOUD_RUN"

echo
echo "==> Probe finished. The phone now has the DEBUG build."
echo "    Put the release build back with:  ./scripts/deploy_ios.sh"
