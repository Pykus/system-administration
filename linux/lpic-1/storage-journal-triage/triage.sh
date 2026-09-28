#!/usr/bin/env bash
set -u

SINCE="30 minutes ago"
TARGET="/var"

usage() {
  cat <<'EOF'
Usage: triage.sh [--since TIME] [--path PATH]

Read-only Linux storage and journal triage.

Examples:
  ./triage.sh
  ./triage.sh --since "2 hours ago" --path /var
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --since)
      [[ $# -ge 2 ]] || { echo "Missing value for --since" >&2; exit 2; }
      SINCE="$2"
      shift 2
      ;;
    --path)
      [[ $# -ge 2 ]] || { echo "Missing value for --path" >&2; exit 2; }
      TARGET="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -d "$TARGET" ]]; then
  echo "Target directory does not exist: $TARGET" >&2
  exit 2
fi

section() {
  printf '\n==== %s ====\n' "$1"
}

section "Filesystem capacity"
df -hP

section "Inode usage"
df -iP

section "Failed systemd units"
if command -v systemctl >/dev/null 2>&1; then
  systemctl --failed --no-pager || true
else
  echo "systemctl is not available"
fi

section "Recent journal warnings"
if command -v journalctl >/dev/null 2>&1; then
  journalctl -p warning..alert --since "$SINCE" --no-pager || true
else
  echo "journalctl is not available"
fi

section "Top-level usage under $TARGET"
if command -v du >/dev/null 2>&1; then
  du -x -h --max-depth=1 "$TARGET" 2>/dev/null | sort -h
else
  echo "du is not available"
fi
