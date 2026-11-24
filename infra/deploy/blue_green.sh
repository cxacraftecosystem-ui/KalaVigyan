#!/usr/bin/env bash
set -euo pipefail

APP="${APP:-/opt/kalavigyan}"
SITE="${NGINX_SITE:-/etc/nginx/sites-available/kalavigyan}"
ENV_FILE="${ENV_FILE:-$APP/.env}"
HEALTH_LIMIT="${HEALTH_LIMIT:-300}"
DRAIN="${DRAIN:-5}"
UNIT=kv-api
WORKERS=(kv-worker kv-fetcher kv-contributions)
RUN_AS=kalavigyan
ALIVE=/health
READY=/health/ready

say() { printf '%s\n' "$*" >&2; }
die() { say "::error::$*"; exit 1; }
NGINX_SWITCH_SECONDS="${NGINX_SWITCH_SECONDS:-20}"
EMBED_SECONDS="${EMBED_SECONDS:-240}"
EMBED_GRACE="${EMBED_GRACE:-60}"
CHECK_SECONDS="${CHECK_SECONDS:-180}"
PAGES_SECONDS="${PAGES_SECONDS:-480}"
DOCUMENTS_SECONDS="${DOCUMENTS_SECONDS:-420}"
REFRESH_SECONDS="${REFRESH_SECONDS:-300}"
CLEANUP_SECONDS="${CLEANUP_SECONDS:-240}"
STATE="${STATE_DIR:-$APP/state}"

other() { if [ "$1" = 8000 ]; then echo 8001; else echo 8000; fi; }
active() { systemctl is-active --quiet "$1" 2>/dev/null; }

live_port() {
  local p
  p="$(sed -nE 's#^[[:space:]]*proxy_pass http://127\.0\.0\.1:([0-9]+);.*#\1#p' "$SITE" | head -n1)"
  case "$p" in 8000|8001) echo "$p" ;; *) die "$SITE proxies to '${p:-nothing}', not 127.0.0.1:8000 or :8001" ;; esac
}

live_unit() {
  if active "$UNIT@$1"; then echo "$UNIT@$1"; fi
}

point() { ln -sfn "$2" "$1.tmp" && mv -Tf "$1.tmp" "$1"; }

migrate() {
  local tree="$1" tries="$2" attempt
  if [ ! -f "$tree/alembic.ini" ]; then
    say "no alembic.ini in $tree; no migrations to run"
    return 0
  fi
  for attempt in $(seq 1 "$tries"); do
    if (cd "$tree" && runuser -u "$RUN_AS" -- bash -c "set -a; . '$ENV_FILE'; set +a; exec ./.venv/bin/python -m alembic upgrade head"); then
      return 0
    fi
    say "migrate attempt $attempt/$tries failed"
    [ "$attempt" = "$tries" ] || sleep 10
  done
  return 1
}

seed() {
  local tree="$1" module
  if [ ! -f "$tree/alembic.ini" ]; then
    return 0
  fi
  for module in app.scripts.seed_crafts app.scripts.seed_claims app.scripts.seed_districts app.scripts.sync_dataset_registry app.scripts.import_curation app.scripts.refresh_shared_terms; do
    if ! (cd "$tree" && runuser -u "$RUN_AS" -- bash -c "set -a; . '$ENV_FILE'; set +a; exec ./.venv/bin/python -m $module" >&2); then
      return 1
    fi
    say "$module done"
  done
  sync_portal_crafts "$tree"
  embed_seeded "$tree" app.scripts.embed_craft_descriptors
  embed_seeded "$tree" app.scripts.embed_knowledge
}

rebuild_pages() {
  local tree="$1" report
  if report="$(cd "$tree" && timeout "$((PAGES_SECONDS + DOCUMENTS_SECONDS + EMBED_GRACE))" runuser -u "$RUN_AS" -- bash -c "set -a; . '$ENV_FILE'; set +a; exec ./.venv/bin/python -m app.scripts.rebuild_stale_pages --seconds $PAGES_SECONDS --document-seconds $DOCUMENTS_SECONDS")"; then
    say "app.scripts.rebuild_stale_pages done: $report"
  else
    say "::warning::app.scripts.rebuild_stale_pages did not finish (${report:-no report}); the release goes on and the nightly upkeep rebuilds what is left; until then reads serve the last good copy of each stored document and queue its rebuild."
  fi
}

refresh_served_pages() {
  local tree="$1" report
  install -d -o "$RUN_AS" -g "$RUN_AS" -m 0750 "$STATE"
  if report="$(cd "$tree" && timeout "$((REFRESH_SECONDS + EMBED_GRACE))" runuser -u "$RUN_AS" -- bash -c "set -a; . '$ENV_FILE'; set +a; exec ./.venv/bin/python -m app.scripts.refresh_served_pages --state '$STATE/served-pages.json' --seconds $REFRESH_SECONDS")"; then
    say "app.scripts.refresh_served_pages done: $report"
  else
    say "::warning::app.scripts.refresh_served_pages did not finish (${report:-no report}); the web keeps the pages it holds until they expire, and the next release refreshes what changed."
  fi
}

sync_portal_crafts() {
  local tree="$1"
  if (cd "$tree" && runuser -u "$RUN_AS" -- bash -c "set -a; . '$ENV_FILE'; set +a; exec ./.venv/bin/python -m app.scripts.sync_portal_crafts" >&2); then
    say "app.scripts.sync_portal_crafts done"
  else
    say "::warning::craft sync from the portals failed; the release goes on with the crafts already stored. The JSON report above names each portal's outcome."
  fi
}

embed_seeded() {
  local tree="$1" module="$2" report
  if report="$(cd "$tree" && timeout "$((EMBED_SECONDS + EMBED_GRACE))" runuser -u "$RUN_AS" -- bash -c "set -a; . '$ENV_FILE'; set +a; exec ./.venv/bin/python -m $module --seconds $EMBED_SECONDS")"; then
    say "$module done: $report"
  else
    say "::warning::$module did not finish (${report:-no report}); the release goes on and the daily Coverage enrichment run embeds what is left."
  fi
}

check_retrieval() {
  local tree="$1" report status=0
  report="$(cd "$tree" && timeout "$((CHECK_SECONDS + EMBED_GRACE))" runuser -u "$RUN_AS" -- bash -c "set -a; . '$ENV_FILE'; [ ! -f ../release.env ] || . ../release.env; set +a; exec ./.venv/bin/python -m app.scripts.eval_retrieval --release --seconds $CHECK_SECONDS")" || status=$?
  case "$status" in
    0) say "retrieval check passed: $report" ;;
    2) say "::warning::the retrieval check warned: $report; the release goes on." ;;
    3) say "::error::retrieval fell below its floor on this release: $report"; return 1 ;;
    *) say "::warning::the retrieval check did not finish (exit $status: ${report:-no report}); the release goes on." ;;
  esac
}

wait_answering() {
  local port="$1" path="$2" start now next_note
  start="$(date +%s)"; next_note=$((start + 20))
  while :; do
    if curl -fsS -m 5 "http://127.0.0.1:$port$path" >/dev/null 2>&1; then
      say "port $port answered $path after $(( $(date +%s) - start ))s"; return 0
    fi
    now="$(date +%s)"
    if [ "$now" -ge $((start + HEALTH_LIMIT)) ]; then return 1; fi
    if [ "$now" -ge "$next_note" ]; then
      say "waiting for $path on $port: $((now - start))s of ${HEALTH_LIMIT}s; $UNIT@$port is $(systemctl is-active "$UNIT@$port" 2>/dev/null || true)"
      next_note=$((now + 20))
    fi
    sleep 2
  done
}

nginx_answers_health() {
  local waited=0
  until curl -fsS -m 5 -o /dev/null http://127.0.0.1/health; do
    [ "$waited" -lt "$NGINX_SWITCH_SECONDS" ] || return 1
    sleep 1
    waited=$((waited + 1))
  done
}

switch_nginx() {
  local port="$1" backup
  backup="$(mktemp)"
  cp "$SITE" "$backup"
  sed -i -E "s#^([[:space:]]*proxy_pass http://127\.0\.0\.1:)[0-9]+;#\1$port;#" "$SITE"
  if [ "$(live_port)" != "$port" ] || ! nginx -t >/dev/null 2>&1; then
    cp "$backup" "$SITE"; rm -f "$backup"
    die "nginx refused the switch to $port; its config is as it was"
  fi
  systemctl reload nginx
  if ! nginx_answers_health; then
    cp "$backup" "$SITE"; rm -f "$backup"
    systemctl reload nginx
    die "nginx did not answer /health after the switch to $port; it was switched back"
  fi
  rm -f "$backup"
  say "nginx now proxies to $port"
}

stop_workers() {
  local w
  workers_were=()
  for w in "${WORKERS[@]}"; do
    if active "$w"; then workers_were+=("$w"); fi
    systemctl stop "$w" 2>/dev/null || true
  done
}

start_workers() {
  local w
  for w in "${WORKERS[@]}"; do
    systemctl enable "$w" >/dev/null 2>&1 || true
    systemctl restart "$w" 2>/dev/null || say "::warning::$w did not start; read: journalctl -u $w -n 80"
  done
  workers_restarted=yes
}

promote() {
  local port="$1" old="$2" rel
  rel="$(readlink -f "$APP/slot-$port")"
  switch_nginx "$port"
  handed_over=yes
  systemctl enable "$UNIT@$port" >/dev/null 2>&1 || say "::warning::could not enable $UNIT@$port"
  if [ -n "$old" ] && [ "$old" != "$UNIT@$port" ]; then
    sleep "$DRAIN"
    systemctl stop "$old" || say "::warning::could not stop $old"
    systemctl disable "$old" >/dev/null 2>&1 || true
  fi
  point "$APP/current" "$rel"
  touch "$rel/.released"
  say "current -> $(readlink "$APP/current")"
}

start_and_promote() {
  systemctl reset-failed "$UNIT@$cand" 2>/dev/null || true
  systemctl start "$UNIT@$cand"
  cand_started=yes
  if ! wait_answering "$cand" "$READY"; then
    say "$UNIT@$cand did not answer $READY within ${HEALTH_LIMIT}s:"
    journalctl -u "$UNIT@$cand" -n 80 --no-pager || true
    die "$UNIT@$cand did not become ready: it must start and reach its database. nginx still proxies to $(other "$cand")."
  fi
  promote "$cand" "$old_unit"
  start_workers
}

put_slot_back() {
  if [ "$(readlink "$APP/slot-$cand" 2>/dev/null || true)" = "$slot_was" ]; then return 0; fi
  if [ -z "$slot_was" ]; then
    rm -f "$APP/slot-$cand"
  elif point "$APP/slot-$cand" "$slot_was"; then
    say "slot-$cand points at $slot_was again, the release it held before"
  else
    say "::warning::slot-$cand could not be pointed back at $slot_was"
  fi
}

on_exit() {
  local rc=$? w
  if [ "$handed_over" != yes ]; then
    if [ "$cand_started" = yes ]; then systemctl stop "$UNIT@$cand" 2>/dev/null || true; fi
    put_slot_back
    if [ "$old_stopped" = yes ] && [ -n "$old_unit" ]; then
      say "restarting $old_unit, which was stopped for the migration"
      systemctl start "$old_unit" || true
    fi
  fi
  if [ "$workers_restarted" != yes ]; then
    for w in "${workers_were[@]}"; do systemctl start "$w" 2>/dev/null || true; done
  fi
  exit "$rc"
}

begin() {
  workers_were=(); old_stopped=no; cand_started=no; handed_over=no; workers_restarted=no
  slot_was="$(readlink "$APP/slot-$cand" 2>/dev/null || true)"
  trap 'on_exit' EXIT
}

serve_again() {
  local port="$1"
  [ "$old_stopped" = yes ] || return 0
  say "migrations passed; starting $old_unit again so it serves while the release seeds and checks"
  systemctl start "$old_unit" || true
  if wait_answering "$port" "$ALIVE"; then
    old_stopped=no
  else
    say "::warning::$old_unit did not answer $ALIVE after the migration; nginx proxies to a stopped port until this release is promoted"
  fi
}

migrate_serving() {
  local tree="$1" live="$2"
  if migrate "$tree" 3; then return 0; fi
  if [ -n "$old_unit" ]; then
    say "::warning::migrations failed three times with $old_unit serving; stopping it to free its pooler sessions and trying again"
    systemctl stop "$old_unit" || true
    old_stopped=yes
    sleep 5
  fi
  migrate "$tree" 5 || die "migrations failed. nginx still proxies to $live."
  serve_again "$live"
}

cmd_release() {
  local id="${1:-}" rel tree live
  [ -n "$id" ] || die "release needs the release id"
  rel="$APP/releases/$id"; tree="$rel/backend"
  [ -x "$tree/.venv/bin/python" ] || die "$tree has no venv"
  [ -s "$ENV_FILE" ] || die "$ENV_FILE is missing or empty"
  live="$(live_port)"
  cand="$(other "$live")"
  old_unit="$(live_unit "$live")"
  if [ "$(readlink -f "$APP/slot-$live" 2>/dev/null || true)" = "$(readlink -f "$rel")" ] && [ -n "$old_unit" ]; then
    die "$rel is already what port $live serves"
  fi
  if active "$UNIT@$cand"; then
    say "stopping $UNIT@$cand: it is running but nginx does not send it traffic"
    systemctl stop "$UNIT@$cand"
  fi
  begin
  point "$APP/slot-$cand" "$rel"
  say "live port $live ($(readlink -f "$APP/current" 2>/dev/null || echo nothing)); this release goes to $cand"
  stop_workers
  migrate_serving "$tree" "$live"
  seed "$tree" || die "seeding failed. nginx still proxies to $live."
  check_retrieval "$tree" || die "retrieval fell below its floor. nginx still proxies to $live."
  start_and_promote
  rebuild_pages "$tree"
  refresh_served_pages "$tree"
  say "released: nginx -> $cand, current -> $(readlink "$APP/current")"
}

cmd_rollback() {
  local live target named="${1:-}"
  live="$(live_port)"; cand="$(other "$live")"
  old_unit="$(live_unit "$live")"
  begin
  if [ -n "$named" ]; then
    target="$APP/releases/$named"
    [ -d "$target" ] || die "no release $named under $APP/releases"
    point "$APP/slot-$cand" "$target"
  fi
  target="$(readlink -f "$APP/slot-$cand" 2>/dev/null || true)"
  [ -x "$target/backend/.venv/bin/python" ] || die "port $cand has no runnable release behind it (${target:-none}); name one: rollback <release>"
  [ -n "$named" ] || [ -f "$target/.released" ] || die "port $cand holds $target, which has never served (a release that stopped before its switch); name the release to go back to: rollback <release>"
  stop_workers
  if active "$UNIT@$cand"; then systemctl stop "$UNIT@$cand"; fi
  start_and_promote
  rebuild_pages "$target/backend"
  refresh_served_pages "$target/backend"
  say "rolled back: nginx -> $cand ($target)"
}

cmd_restart() {
  local live rel
  live="$(live_port)"; cand="$(other "$live")"
  rel="$(readlink -f "$APP/slot-$live" 2>/dev/null || true)"
  [ -x "$rel/backend/.venv/bin/python" ] || die "port $live has no runnable release behind it (${rel:-none})"
  old_unit="$(live_unit "$live")"
  if active "$UNIT@$cand"; then systemctl stop "$UNIT@$cand"; fi
  begin
  point "$APP/slot-$cand" "$rel"
  start_and_promote
  if [ -n "$slot_was" ]; then point "$APP/slot-$live" "$slot_was"; fi
  say "restarted $rel on port $cand with the environment as rendered now; port $live holds $(readlink -f "$APP/slot-$live" 2>/dev/null || echo 'no release')"
}

release_within() {
  local id="$1" seconds="$2"
  [[ "$seconds" =~ ^[1-9][0-9]*$ ]] || die "--within takes whole seconds, not '$seconds'"
  say "this release stops itself after ${seconds}s and puts the box back as it was"
  exec timeout --signal=TERM --kill-after="$CLEANUP_SECONDS" "$seconds" "$BASH" "$0" release "$id"
}

cmd_status() {
  local live
  live="$(live_port)"
  echo "nginx proxies to: $live"
  echo "live unit:        $(live_unit "$live")"
  echo "current ->        $(readlink -f "$APP/current" 2>/dev/null || echo missing)"
  for p in 8000 8001; do
    echo "port $p:        $(systemctl is-active "$UNIT@$p" 2>/dev/null || true), $(readlink -f "$APP/slot-$p" 2>/dev/null || echo 'no release')"
  done
  for w in "${WORKERS[@]}"; do echo "$w: $(systemctl is-active "$w" 2>/dev/null || true)"; done
}

[ "$(id -u)" = 0 ] || die "run as root (SSM runs commands as root)"
case "${1:-}" in
  release)
    shift
    if [ "${2:-}" = --within ]; then release_within "$1" "${3:-}"; fi
    cmd_release "$@" ;;
  rollback) shift; cmd_rollback "$@" ;;
  restart) cmd_restart ;;
  status) cmd_status ;;
  *) die "usage: blue_green.sh release <id> [--within <seconds>] | rollback [release] | restart | status" ;;
esac
