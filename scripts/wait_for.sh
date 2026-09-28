#!/usr/bin/env bash
# Polls a URL until it answers 2xx/3xx, or fails after N seconds.
# Usage: wait_for.sh <url> <timeout_seconds>
set -euo pipefail

url="${1:?usage: wait_for.sh <url> <timeout_seconds>}"
timeout="${2:?usage: wait_for.sh <url> <timeout_seconds>}"
started=$SECONDS
last_status=000

while true; do
  last_status=$(curl --connect-timeout 2 --max-time 5 -sS -o /dev/null \
    -w '%{http_code}' "$url" 2>/dev/null || true)
  if [[ "$last_status" =~ ^[23][0-9]{2}$ ]]; then
    elapsed=$((SECONDS - started))
    echo "wait_for.sh: $url ready after ${elapsed}s (HTTP ${last_status})"
    exit 0
  fi

  elapsed=$((SECONDS - started))
  if [ "$elapsed" -ge "$timeout" ]; then
    echo "wait_for.sh: $url not ready after ${elapsed}s (limit ${timeout}s; last HTTP status ${last_status})" >&2
    exit 1
  fi
  sleep 1
done
