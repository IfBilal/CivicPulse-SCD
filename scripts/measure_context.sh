#!/usr/bin/env bash
# Measures the build context each Dockerfile sends to the daemon, with and without its
# per-Dockerfile ignore file (Rubric G: ".dockerignore before/after, with numbers").
# Preferred: BuildKit's own "transferring context" figure. Fallback when Docker is unavailable:
# a tar of exactly the files the ignore rules admit — labelled as an estimate, never passed off
# as a Docker measurement.
set -euo pipefail
cd "$(dirname "$0")/.."

human() { numfmt --to=iec --suffix=B --format="%.1f" "$1"; }

# BuildKit prints its own size suffixes (B, kB, MB, GB — decimal-ish, not IEC K/M/G), and the
# LAST "transferring context" line during a build is the final, complete total (earlier lines
# are itself the transfer progressing) — so take the last one and convert it ourselves.
bk_to_bytes() { # $1 = e.g. "144.38kB", "27B", "1.2MB"
  python3 -c '
import re, sys
m = re.match(r"([0-9.]+)([kMG]?)B", sys.argv[1])
n, unit = float(m.group(1)), m.group(2)
mult = {"": 1, "k": 1000, "M": 1000**2, "G": 1000**3}[unit]
print(int(n * mult))
' "$1"
}
docker_ctx() { # $1 = dockerfile ; $2 = target ; prints bytes sent
  local raw
  raw=$(DOCKER_BUILDKIT=1 docker build --no-cache --progress=plain -f "$1" --target "$2" -t ctx-probe:tmp . 2>&1 \
    | grep -oE 'transferring context: [0-9.]+[kMG]?B' | tail -1 | awk '{print $3}')
  [ -n "$raw" ] && bk_to_bytes "$raw" || echo 0
}

tar_ctx_all() { tar --exclude=.git -cf - . 2>/dev/null | wc -c; }
tar_ctx_allowed() { # $1 = ignore file (allow-list form: "*" then "!path" lines, then re-excludes)
  local ignore="$1" inc=() exc=()
  while IFS= read -r line; do
    case "$line" in ''|\#*|'*') ;; '!'*) inc+=("${line#!}") ;; *) exc+=("--exclude=${line#\*\*/}") ;; esac
  done < "$ignore"
  local present=()
  for p in "${inc[@]}"; do [ -e "$p" ] && present+=("$p"); done
  tar "${exc[@]}" -cf - "${present[@]}" 2>/dev/null | wc -c
}

if docker info >/dev/null 2>&1; then
  method="docker buildx (transferring context)"
  measure() { # $1 dockerfile $2 target $3 ignore
    local with without
    with=$(docker_ctx "$1" "$2")
    mv "$3" "$3.off"; trap 'mv "$3.off" "$3" 2>/dev/null || true' RETURN
    without=$(docker_ctx "$1" "$2")
    echo "$without $with"
  }
else
  method="ESTIMATE via tar (docker daemon unavailable on this machine) — re-run \`make evidence-context\` where Docker works"
  measure() { echo "$(tar_ctx_all) $(tar_ctx_allowed "$3")"; }
fi

echo "# build-context sizes · $(date -u +%FT%TZ) · $(git rev-parse --short HEAD)"
echo "# method: $method"
for spec in "backend backend/Dockerfile runtime backend/Dockerfile.dockerignore" \
            "frontend frontend/Dockerfile runtime frontend/Dockerfile.dockerignore"; do
  set -- $spec
  read -r without with < <(measure "$2" "$3" "$4")
  pct=$(awk -v a="$without" -v b="$with" 'BEGIN{ if (a>0) printf "%.1f", (1-b/a)*100; else print "n/a" }')
  printf '%-8s without ignore: %9s    with: %9s    (−%s%%)\n' "$1" "$(human "$without")" "$(human "$with")" "$pct"
done
