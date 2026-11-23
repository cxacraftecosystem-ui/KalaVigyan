#!/usr/bin/env bash
set -u
url=""
for arg in "$@"; do
  case "$arg" in http://*) url="$arg" ;; esac
done
rest="${url#http://127.0.0.1}"
case "$rest" in
  :*)
    port="${rest#:}"
    port="${port%%/*}"
    path="/${rest#*/}" ;;
  *)
    port="$(sed -nE 's#^[[:space:]]*proxy_pass http://127\.0\.0\.1:([0-9]+);.*#\1#p' "$NGINX_SITE" | head -n1)"
    path="$rest" ;;
esac
unit="$BOX/units/kv-api@$port"
[ -e "$unit" ] || exit 7
if [ "$path" = /health/ready ] && [ -e "$unit.unready" ]; then exit 22; fi
exit 0
