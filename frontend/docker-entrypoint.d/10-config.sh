#!/bin/sh
# Runs at container start (nginx image entrypoint) as the non-root `app` user.
# 1) /config.js — non-URL runtime flags, so ONE image serves every environment (ADR-0002).
# 2) /tmp/nginx/runtime.conf — DNS resolver + backend upstream for the /api proxy.
# Values are validated before they are written: config.js is served to every browser, so an
# unvalidated env var here would be a script-injection vector. Never put a credential in it.
set -eu

fail() { echo "10-config.sh: $1" >&2; exit 1; }
is_word() { case "$1" in ''|*[!A-Za-z0-9._-]*) return 1 ;; esac; }
is_int()  { case "$1" in ''|*[!0-9]*) return 1 ;; esac; }

APP_ENV="${APP_ENV:-dev}"
GIT_SHA="${GIT_SHA:-dev}"
STATS_POLL_MS="${STATS_POLL_MS:-15000}"
SHOW_CACHE_BADGE="${SHOW_CACHE_BADGE:-true}"
BACKEND_UPSTREAM="${BACKEND_UPSTREAM:-backend:8000}"

is_word "$APP_ENV" || fail "APP_ENV must match [A-Za-z0-9._-]+"
is_word "$GIT_SHA" || fail "GIT_SHA must match [A-Za-z0-9._-]+"
is_int "$STATS_POLL_MS" || fail "STATS_POLL_MS must be an integer (ms)"
case "$SHOW_CACHE_BADGE" in true|false) ;; *) fail "SHOW_CACHE_BADGE must be true|false" ;; esac
case "$BACKEND_UPSTREAM" in ''|*[!A-Za-z0-9.:-]*) fail "BACKEND_UPSTREAM must be host:port" ;; esac

cat > /usr/share/nginx/html/config.js <<JS
window.__CIVICPULSE__ = { env: "${APP_ENV}", version: "${GIT_SHA}", statsPollMs: ${STATS_POLL_MS}, showCacheBadge: ${SHOW_CACHE_BADGE} };
JS

mkdir -p /tmp/nginx
NAMESERVER="$(awk '/^nameserver/ { print $2; exit }' /etc/resolv.conf)"
[ -n "$NAMESERVER" ] || fail "no nameserver in /etc/resolv.conf"
case "$NAMESERVER" in *:*) NAMESERVER="[$NAMESERVER]" ;; esac
cat > /tmp/nginx/runtime.conf <<CONF
resolver ${NAMESERVER} valid=10s ipv6=off;
set \$backend_upstream ${BACKEND_UPSTREAM};
CONF
echo "10-config.sh: env=${APP_ENV} version=${GIT_SHA} upstream=${BACKEND_UPSTREAM} resolver=${NAMESERVER}"
