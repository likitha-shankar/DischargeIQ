#!/usr/bin/env bash
#
# scripts/build_beta_kit.sh
#
# Sprint 2, Task 2.5 - Assemble the Android beta tester kit into a single
# shareable folder + zip. Owner: Likitha Shankar.
#
# Bundles: the arm64 release APK (the one to send testers), the onboarding
# guide, and three synthetic discharge PDFs (one per common diagnosis) so a
# tester has everything to install and run without repo access.
#
# The release APK already points at the hosted Cloud Run backend (see
# lib/config.dart), so it works on any network with no local server.
#
# Output (dist/ is gitignored - build artifacts, not source):
#   dist/beta_kit/            the folder to share
#   dist/DischargeIQ-beta-kit.zip
#
# Usage:
#   flutter build apk --release --split-per-abi   # if the APK is stale
#   bash scripts/build_beta_kit.sh

set -euo pipefail
cd "$(dirname "$0")/.."

APK="dischargeiq_mobile/build/app/outputs/flutter-apk/app-arm64-v8a-release.apk"
KIT="dist/beta_kit"
SAMPLES=(heart_failure_01 copd_01 hip_replacement_01)

if [ ! -f "$APK" ]; then
  echo "ERROR: $APK not found."
  echo "Build it first: (cd dischargeiq_mobile && flutter build apk --release --split-per-abi)"
  exit 1
fi

rm -rf "$KIT"
mkdir -p "$KIT/sample-documents"

# APK - rename to something a tester recognizes.
cp "$APK" "$KIT/DischargeIQ.apk"

# Onboarding guide.
cp docs/beta/ONBOARDING.md "$KIT/READ-ME-FIRST.md"

# Three synthetic documents, one per common diagnosis. Synthetic only -
# never ship a real discharge document (repo hard rule 6).
for name in "${SAMPLES[@]}"; do
  src="test-data/synthetic/${name}.pdf"
  [ -f "$src" ] && cp "$src" "$KIT/sample-documents/${name}.pdf" \
    || echo "WARN: $src missing, skipped"
done

# Manifest so the tester (and you) can see exactly what's in the kit.
{
  echo "DischargeIQ Android Beta Kit"
  echo "Built: $(date '+%Y-%m-%d %H:%M')"
  echo "Backend: hosted Cloud Run (no local server needed)"
  echo ""
  echo "Contents:"
  echo "  DischargeIQ.apk        - install this (arm64, modern Android phones)"
  echo "  READ-ME-FIRST.md       - setup + what to test"
  echo "  sample-documents/      - synthetic discharge PDFs to try (NOT real patients)"
} > "$KIT/MANIFEST.txt"

ZIP="dist/DischargeIQ-beta-kit.zip"
rm -f "$ZIP"
(cd dist && zip -rq "$(basename "$ZIP")" beta_kit)

echo "Beta kit ready:"
echo "  Folder: $KIT"
echo "  Zip:    $ZIP  ($(du -h "$ZIP" | cut -f1))"
echo "Share the zip (or upload DischargeIQ.apk to Drive and send the link)."
