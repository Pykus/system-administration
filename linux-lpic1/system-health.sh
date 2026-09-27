#!/usr/bin/env bash
set -euo pipefail
printf '== host ==\n'
hostnamectl 2>/dev/null || hostname
printf '\n== filesystem ==\n'
df -hT
printf '\n== memory ==\n'
free -h
printf '\n== failed services ==\n'
if command -v systemctl >/dev/null 2>&1; then
  systemctl --failed --no-pager || true
else
  printf 'systemd unavailable\n'
fi
printf '\n== listening sockets ==\n'
ss -lntup 2>/dev/null || ss -lnt 2>/dev/null || true
