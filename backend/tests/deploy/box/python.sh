#!/usr/bin/env bash
set -u
module=""
if [ "${1:-}" = -m ]; then module="$2"; fi
port="$(sed -nE 's#^[[:space:]]*proxy_pass http://127\.0\.0\.1:([0-9]+);.*#\1#p' "$NGINX_SITE" | head -n1)"
if [ -e "$BOX/units/kv-api@$port" ]; then serving=served; else serving=unserved; fi
printf '%s %s\n' "$module" "$serving" >> "$BOX/events.log"
if [ "$module" = alembic ]; then
  left="$(cat "$BOX/migration-failures" 2>/dev/null || echo 0)"
  if [ "$left" -gt 0 ]; then
    echo $((left - 1)) > "$BOX/migration-failures"
    exit 1
  fi
fi
if [ "$module" = "$(cat "$BOX/slow-step" 2>/dev/null || true)" ]; then
  exec "$REAL_SLEEP" 20 </dev/null >/dev/null 2>&1
fi
echo '{"ok": true}'
if [ "$module" = app.scripts.eval_retrieval ]; then exit "$(cat "$BOX/check-exit" 2>/dev/null || echo 0)"; fi
exit 0
