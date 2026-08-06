#!/usr/bin/env bash
#
# Pull the DischargeIQ app container off the iPhone, or push a backup back.
#
# WHY THIS EXISTS: on Aug 4, 2026 a deploy used `flutter install`, which
# uninstalls before installing. An iOS uninstall deletes the app container, so
# the on-device document library, the saved PDFs, every profile, and all
# gamification progress were destroyed with no copy anywhere. None of that
# lives on the server by design - the backend stores only structured fields
# (see CLAUDE.md), never the agent prose or the PDFs. A container copy is the
# ONLY way to preserve it, and it takes one command.
#
# Works because the app is development-signed (get-task-allow), which lets
# devicectl read its data container.
#
# Usage:
#   ./scripts/backup_ios_data.sh backup  [device-udid]
#   ./scripts/backup_ios_data.sh restore <backup-dir> [device-udid]
#
# Backups land in device-backups/<timestamp>/ which is gitignored: they hold
# real discharge documents and must never enter the repo.

set -euo pipefail

BUNDLE_ID="com.likithashankar.dischargeiq"
DEFAULT_UDID="00008120-001A3D281A78C01E"

cd "$(dirname "$0")/.."

# Documents holds the analysed results and stored PDFs; Library/Preferences
# holds the SharedPreferences plist, which is where gamification state (stars,
# blooms, quests, streaks, check-ins) and the active profile live. Caches and
# saved application state are deliberately skipped - they are rebuildable and
# only bloat the copy.
readonly PATHS=("Documents" "Library/Preferences")

_copy_from() {
  # Missing paths are normal on a fresh install, so a failure here is
  # reported and skipped rather than aborting the whole backup.
  xcrun devicectl device copy from \
    --device "$1" --domain-type appDataContainer --domain-identifier "$BUNDLE_ID" \
    --source "$2" --destination "$3" 2>&1 || true
}

do_backup() {
  local udid="$1"
  local dest="device-backups/$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$dest"

  local got_any=0 out
  for path in "${PATHS[@]}"; do
    local target="$dest/$path"
    mkdir -p "$(dirname "$target")"
    echo "==> Pulling $path"
    # Captured, not piped into grep -q: under pipefail that pattern reports
    # the opposite of what happened (grep short-circuits, upstream SIGPIPEs).
    out=$(_copy_from "$udid" "$path" "$target")
    if [[ "$out" == *"File received from Device"* ]]; then
      got_any=1
    else
      echo "    (not present on device - skipping)"
    fi
  done

  if [[ "$got_any" -eq 0 ]]; then
    echo "Nothing to back up: the app has no saved data yet."
    rmdir "$dest" 2>/dev/null || true
    return 0
  fi

  echo "Backed up to $dest"
  du -sh "$dest" 2>/dev/null || true
}

do_restore() {
  local src="$1" udid="$2"
  [[ -d "$src" ]] || { echo "No such backup directory: $src" >&2; exit 1; }

  local failed=0
  for path in "${PATHS[@]}"; do
    [[ -e "$src/$path" ]] || continue
    echo "==> Restoring $path"
    # The wireless link to the phone drops intermittently (CoreDeviceError
    # 4000), so retry before giving up. A restore that half-worked must never
    # report success - that is how data loss gets discovered days later.
    local attempt ok=0 out
    for attempt in 1 2 3; do
      # Capture, then inspect. Matching with `grep -q` on a pipe under
      # `set -o pipefail` misreports the result, because grep short-circuits
      # and SIGPIPEs the upstream command.
      if out=$(xcrun devicectl device copy to \
        --device "$udid" --domain-type appDataContainer \
        --domain-identifier "$BUNDLE_ID" \
        --source "$src/$path" --destination "$path" 2>&1) &&
        [[ "$out" != *"ERROR"* ]]; then
        ok=1
        break
      fi
      echo "    attempt $attempt failed; retrying" >&2
      sleep 3
    done
    [[ "$ok" -eq 1 ]] || { echo "    RESTORE FAILED for $path" >&2; failed=1; }
  done

  if [[ "$failed" -ne 0 ]]; then
    echo "Restore INCOMPLETE - the backup at $src is untouched, try again." >&2
    exit 1
  fi
  echo "Restored from $src. Force-quit and reopen the app to reload it."
}

case "${1:-backup}" in
  backup)  do_backup "${2:-$DEFAULT_UDID}" ;;
  restore) do_restore "${2:?usage: restore <backup-dir> [udid]}" "${3:-$DEFAULT_UDID}" ;;
  *) echo "usage: $0 backup [udid] | restore <backup-dir> [udid]" >&2; exit 1 ;;
esac
