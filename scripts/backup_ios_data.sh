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
#
# THE RULE THIS SCRIPT LIVES BY: it may only report success when it can prove
# it. On Aug 7 a backup announced "the app has no saved data yet" while two
# analysed documents and a profile sat on the phone - the link had dropped
# mid-pull ("Connection reset by peer") and the old success test, a string
# match on devicectl's chatter, simply did not match. It then exited 0, so the
# deploy went ahead and installed over live data believing it held a copy.
# Everything below exists to make that specific lie impossible:
#   - success is decided by counting files that actually landed on disk, not
#     by reading devicectl's wording, which Apple is free to change
#   - a dropped link is retried, and is never confused with "no data"
#   - "nothing to back up" is only ever said when the device answered and
#     genuinely reported the path missing
#   - anything unproven exits non-zero, which aborts deploy_ios.sh (set -e)

set -euo pipefail

BUNDLE_ID="com.likithashankar.dischargeiq"
DEFAULT_UDID="00008120-001A3D281A78C01E"

# The wireless link drops often enough that one attempt proves nothing.
readonly MAX_ATTEMPTS=3
readonly RETRY_SLEEP=3

cd "$(dirname "$0")/.."

# Documents holds the analysed results and stored PDFs; Library/Preferences
# holds the SharedPreferences plist, which is where gamification state (stars,
# blooms, quests, streaks, check-ins) and the active profile live. Caches and
# saved application state are deliberately skipped - they are rebuildable and
# only bloat the copy.
readonly PATHS=("Documents" "Library/Preferences")

# devicectl's message when the container genuinely has no such path. Distinct
# from every transport failure, which is the distinction the old script missed.
readonly ABSENT_MARKER="Failed to retrieve the file node"

# ── helpers ─────────────────────────────────────────────────────────────────

# Can we actually talk to the phone, and is the app installed on it?
# Used as the final arbiter before this script is allowed to claim there is
# no data: an unreachable device can never prove that.
_device_reachable() {
  local out
  out=$(xcrun devicectl device info apps \
    --device "$1" --bundle-id "$BUNDLE_ID" 2>&1) || return 1
  [[ "$out" == *"$BUNDLE_ID"* ]]
}

_file_count() {
  [[ -d "$1" ]] || { echo 0; return; }
  find "$1" -type f 2>/dev/null | wc -l | tr -d ' '
}

# Pull one path, retrying transient failures.
#
# Echoes a verdict: "ok" (files landed), "absent" (device says no such path),
# or "error" (could not be established). Never echoes "absent" for a link
# failure, which is the whole point.
_pull_path() {
  local udid="$1" path="$2" dest="$3" attempt out rc
  for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
    rc=0
    out=$(xcrun devicectl device copy from \
      --device "$udid" --domain-type appDataContainer \
      --domain-identifier "$BUNDLE_ID" \
      --source "$path" --destination "$dest" 2>&1) || rc=$?

    # Ground truth first: files on disk beat anything devicectl says about
    # itself. A partial transfer that left files still counts as data worth
    # keeping, so this is checked before the exit code.
    if [[ "$(_file_count "$dest")" -gt 0 ]]; then
      echo "ok"
      return 0
    fi

    if [[ "$rc" -eq 0 ]]; then
      # Clean exit and nothing on disk: an empty directory on the device.
      echo "absent"
      return 0
    fi

    if [[ "$out" == *"$ABSENT_MARKER"* ]]; then
      # The device answered and said the path is not there. Retrying cannot
      # change that.
      echo "absent"
      return 0
    fi

    [[ "$attempt" -lt "$MAX_ATTEMPTS" ]] && sleep "$RETRY_SLEEP"
  done

  # Exhausted retries without proof either way. Report the last line so the
  # cause is visible rather than guessed at.
  echo "    last error: $(echo "$out" | grep -iE 'error|connection' | tail -1 | cut -c1-120)" >&2
  echo "error"
}

# ── backup ──────────────────────────────────────────────────────────────────

do_backup() {
  local udid="$1"
  local dest="device-backups/$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$dest"

  local got_any=0 had_error=0 verdict
  for path in "${PATHS[@]}"; do
    local target="$dest/$path"
    mkdir -p "$(dirname "$target")"
    echo "==> Pulling $path"
    verdict=$(_pull_path "$udid" "$path" "$target")
    case "$verdict" in
      ok)     got_any=1 ;;
      absent) echo "    (not on device)" ;;
      error)  echo "    COULD NOT READ $path" >&2; had_error=1 ;;
    esac
  done

  if [[ "$got_any" -eq 1 ]]; then
    # Report what was actually captured. A backup that silently holds fewer
    # files than expected is how the Aug 4 loss went unnoticed.
    echo "Backed up to $dest ($(_file_count "$dest") files)"
    du -sh "$dest" 2>/dev/null || true
    if [[ "$had_error" -ne 0 ]]; then
      echo "WARNING: this backup is INCOMPLETE - at least one path could not" >&2
      echo "be read. Do not install over the app until it succeeds cleanly." >&2
      exit 1
    fi
    return 0
  fi

  # Nothing landed, so leave no empty timestamped shell behind to be mistaken
  # for a real backup later. rmdir alone will not do it: the per-path parents
  # (Library/) were created up front and are themselves empty.
  find "$dest" -type d -empty -delete 2>/dev/null || true
  rmdir "$dest" 2>/dev/null || true

  if [[ "$had_error" -ne 0 ]]; then
    echo "BACKUP FAILED: could not read the app container." >&2
    echo "This is NOT the same as the app having no data - the device did not" >&2
    echo "answer. Reconnect the cable and retry before installing anything." >&2
    exit 1
  fi

  # Every path came back cleanly absent. Only trust that if the phone is
  # actually answering us.
  if ! _device_reachable "$udid"; then
    echo "BACKUP FAILED: the device is not reachable, so 'no data' cannot be" >&2
    echo "trusted. Reconnect the cable and retry." >&2
    exit 1
  fi

  echo "Nothing to back up: the app is installed and has no saved data yet."
}

# ── restore ─────────────────────────────────────────────────────────────────

do_restore() {
  local src="$1" udid="$2"
  [[ -d "$src" ]] || { echo "No such backup directory: $src" >&2; exit 1; }

  local failed=0
  for path in "${PATHS[@]}"; do
    [[ -e "$src/$path" ]] || continue
    echo "==> Restoring $path"
    local attempt ok=0 out rc
    for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
      rc=0
      # Exit code, not a string match. The old test looked for "ERROR" in the
      # output, which a dropped link does not print - it says "Connection was
      # invalidated", so a failed push could report success.
      out=$(xcrun devicectl device copy to \
        --device "$udid" --domain-type appDataContainer \
        --domain-identifier "$BUNDLE_ID" \
        --source "$src/$path" --destination "$path" 2>&1) || rc=$?
      if [[ "$rc" -eq 0 && "$out" != *"ERROR"* ]]; then
        ok=1
        break
      fi
      echo "    attempt $attempt failed; retrying" >&2
      sleep "$RETRY_SLEEP"
    done
    [[ "$ok" -eq 1 ]] || { echo "    RESTORE FAILED for $path" >&2; failed=1; }
  done

  if [[ "$failed" -ne 0 ]]; then
    echo "Restore INCOMPLETE - the backup at $src is untouched, try again." >&2
    exit 1
  fi

  _verify_restore "$src" "$udid"
  echo "Restored from $src. Force-quit and reopen the app to reload it."
}

# Read the container back and compare file counts against the backup.
#
# A push that reports success and lands nothing is the failure that costs a
# patient their data, and it is only discovered days later. One round trip is
# cheap insurance against shipping that silently.
_verify_restore() {
  local src="$1" udid="$2"
  local tmp
  tmp=$(mktemp -d)
  # A verification that cannot run is reported, never treated as a pass.
  local mismatch=0
  for path in "${PATHS[@]}"; do
    [[ -e "$src/$path" ]] || continue
    local expected actual
    expected=$(_file_count "$src/$path")
    mkdir -p "$(dirname "$tmp/$path")"
    if [[ "$(_pull_path "$udid" "$path" "$tmp/$path")" != "ok" ]]; then
      echo "    could not verify $path" >&2
      mismatch=1
      continue
    fi
    actual=$(_file_count "$tmp/$path")
    if [[ "$actual" -lt "$expected" ]]; then
      echo "    VERIFY FAILED for $path: $actual of $expected files on device" >&2
      mismatch=1
    else
      echo "    verified $path ($actual files)"
    fi
  done
  rm -rf "$tmp"
  if [[ "$mismatch" -ne 0 ]]; then
    echo "Restore could NOT be verified. Your backup at $src is untouched." >&2
    exit 1
  fi
}

case "${1:-backup}" in
  backup)  do_backup "${2:-$DEFAULT_UDID}" ;;
  restore) do_restore "${2:?usage: restore <backup-dir> [udid]}" "${3:-$DEFAULT_UDID}" ;;
  *) echo "usage: $0 backup [udid] | restore <backup-dir> [udid]" >&2; exit 1 ;;
esac
