#!/usr/bin/env bash
# Dry-run backup retention planner.
#
# Problem:
# Backup directories grow silently. This tool lists files older than a chosen
# age and calculates reclaimable bytes without deleting anything.
#
# Run:
#   ./backup-retention-plan.sh /srv/backups 30
#   ./backup-retention-plan.sh --self-test
#
# Synthetic example:
#   touch -d '45 days ago' /tmp/backups/app-2026-08-01.tar
#   ./backup-retention-plan.sh /tmp/backups 30
# Expected behavior: the old file is printed and the summary reports one
# candidate. No file is ever removed.
set -euo pipefail

if [[ "${1:-}" == "--self-test" ]]; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  printf x > "$tmp/old.tar"
  printf yy > "$tmp/new.tar"
  touch -d '45 days ago' "$tmp/old.tar"
  touch -d '2 days ago' "$tmp/new.tar"
  out="$("$0" "$tmp" 30)"
  grep -q 'old.tar' <<<"$out"
  ! grep -q 'new.tar' <<<"$out"
  grep -q 'SUMMARY candidates=1 bytes=1' <<<"$out"
  echo SELF_TEST_OK
  exit 0
fi

root="${1:-}"
days="${2:-30}"
[[ -n "$root" ]] || { echo "Usage: $0 DIRECTORY [DAYS] | --self-test" >&2; exit 2; }
[[ -d "$root" ]] || { echo "ERROR directory not found: $root" >&2; exit 1; }
[[ "$days" =~ ^[0-9]+$ ]] || { echo "ERROR DAYS must be a non-negative integer" >&2; exit 2; }

count=0
bytes=0
while IFS= read -r -d '' file; do
  size="$(stat -c %s "$file")"
  printf 'CANDIDATE %s bytes=%s\n' "$file" "$size"
  count=$((count+1))
  bytes=$((bytes+size))
done < <(find "$root" -type f -mtime "+$days" -print0 | sort -z)
printf 'SUMMARY candidates=%s bytes=%s\n' "$count" "$bytes"