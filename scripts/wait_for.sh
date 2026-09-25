#!/usr/bin/env bash
# Polls a URL until it answers 2xx/3xx, or fails after N seconds.
# Usage: wait_for.sh <url> <timeout_seconds>
set -euo pipefail

url="${1:?usage: wait_for.sh <url> <timeout_seconds>}"
timeout="${2:?usage: wait_for.sh <url> <timeout_seconds>}"
elapsed=0

until curl -sf -o /dev/null "$url"; do
  if [ "$elapsed" -ge "$timeout" ]; then
    echo "wait_for.sh: $url not ready after ${timeout}s" >&2
    exit 1
  fi
  sleep 1
  elapsed=$((elapsed + 1))
done

echo "wait_for.sh: $url ready after ${elapsed}s"
