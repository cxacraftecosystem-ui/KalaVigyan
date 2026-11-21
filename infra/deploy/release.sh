#!/usr/bin/env bash
set -euo pipefail

SHA="${1:?release needs the commit sha}"
TARBALL="${2:?release needs the tarball path}"
KEEP="${KEEP_RELEASES:-5}"
. /etc/kalavigyan/box.env
APP="${KV_APP:-/opt/kalavigyan}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REL="$APP/releases/$SHA"
PIN="$HERE/python.pin"

say() { printf '%s\n' "$*" >&2; }
die() { say "::error::$*"; exit 1; }
pinned() { sed -n "s/^$1=//p" "$PIN"; }

[ "$(id -u)" = 0 ] || die "run as root"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || die "release id must be a full commit sha"
command -v uv >/dev/null || die "uv is not installed"
[ -f "$PIN" ] || die "$PIN is missing; the release does not say which CPython it runs on"
PY_VERSION="$(pinned PY_VERSION)"
PY_BUILD="$(pinned PY_BUILD)"
PY_URL="$(pinned PY_URL)"
PY_SHA256="$(pinned PY_SHA256)"
[[ "$PY_VERSION" =~ ^3\.[0-9]+\.[0-9]+$ ]] || die "$PIN: PY_VERSION '$PY_VERSION' is not a CPython release"
[[ "$PY_BUILD" =~ ^[0-9]{8}$ ]] || die "$PIN: PY_BUILD '$PY_BUILD' is not a python-build-standalone release"
[[ "$PY_URL" == https://github.com/astral-sh/python-build-standalone/releases/download/* ]] || die "$PIN: PY_URL is not an https python-build-standalone download"
[[ "$PY_SHA256" =~ ^[0-9a-f]{64}$ ]] || die "$PIN: PY_SHA256 is not a sha256"
PY_MINOR="${PY_VERSION%.*}"
PY_HOME="/opt/cpython/${PY_VERSION}+${PY_BUILD}"
PYTHON="$PY_HOME/bin/python${PY_MINOR}"

install_units() {
  local changed=no f name
  for f in "$HERE"/units/*; do
    name="$(basename "$f")"
    if ! cmp -s "$f" "/etc/systemd/system/$name"; then
      install -m 0644 "$f" "/etc/systemd/system/$name"
      changed=yes
      say "installed /etc/systemd/system/$name"
    fi
  done
  if ! cmp -s "$HERE/api-watchdog.sh" /usr/local/bin/api-watchdog.sh; then
    install -m 0755 "$HERE/api-watchdog.sh" /usr/local/bin/api-watchdog.sh
  fi
  if ! cmp -s "$HERE/blue_green.sh" /usr/local/sbin/kv-blue-green; then
    install -m 0755 "$HERE/blue_green.sh" /usr/local/sbin/kv-blue-green
  fi
  if ! cmp -s "$HERE/render_env.sh" /usr/local/sbin/kv-render-env; then
    install -m 0755 "$HERE/render_env.sh" /usr/local/sbin/kv-render-env
  fi
  if [ "$changed" = yes ]; then systemctl daemon-reload; fi
  systemctl enable --now api-watchdog.timer >/dev/null 2>&1 || say "::warning::api-watchdog.timer did not start"
}

stage_python() {
  local stage="$1"
  curl -fsSL --proto '=https' --tlsv1.2 --retry 5 --retry-delay 10 --retry-all-errors --connect-timeout 30 --max-time 900 -o "$stage/python.tar.gz" "$PY_URL" \
    && echo "${PY_SHA256}  $stage/python.tar.gz" | sha256sum -c - >&2 \
    && tar -xzf "$stage/python.tar.gz" -C "$stage" --no-same-owner \
    && { "$stage/python/bin/python${PY_MINOR}" -I -m compileall -q "$stage/python/lib/python${PY_MINOR}" >/dev/null || true; } \
    && chown -R root:root "$stage/python" \
    && chmod -R go-w "$stage/python"
}

install_python() {
  local stage
  if [ -e "$PY_HOME" ]; then
    say "CPython ${PY_VERSION}+${PY_BUILD} is already installed in $PY_HOME"
  else
    install -d -o root -g root -m 0755 /opt/cpython
    stage="$(mktemp -d /opt/cpython/.incoming.XXXXXX)"
    if ! stage_python "$stage" || ! mv -T "$stage/python" "$PY_HOME"; then
      rm -rf "$stage"
      die "CPython ${PY_VERSION}+${PY_BUILD} could not be installed from $PY_URL; nothing was changed"
    fi
    rm -rf "$stage"
    say "installed CPython ${PY_VERSION}+${PY_BUILD} in $PY_HOME"
  fi
  "$PYTHON" -I -c 'import sys, platform, ssl, sqlite3, venv; assert platform.python_version() == sys.argv[1]; print("CPython", platform.python_version(), ssl.OPENSSL_VERSION)' "$PY_VERSION" >&2 \
    || die "$PYTHON is not a working CPython $PY_VERSION"
}

build_release() {
  if [ -f "$REL/.complete" ]; then
    say "$REL is already built; reusing it"
    return 0
  fi
  install_python
  rm -rf "$REL"
  install -d -o root -g kalavigyan -m 0755 "$REL"
  tar -xzf "$TARBALL" -C "$REL" --no-same-owner
  [ -f "$REL/backend/pyproject.toml" ] || die "the tarball has no backend/pyproject.toml"
  local args=(sync --no-dev --no-editable --python "$PYTHON")
  if [ -f "$REL/backend/uv.lock" ]; then args+=(--frozen); else say "::warning::backend/uv.lock is missing; resolving dependencies on the box"; fi
  (
    cd "$REL/backend"
    export UV_CACHE_DIR=/var/cache/kalavigyan-uv UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT="$REL/backend/.venv" UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
    uv "${args[@]}"
  ) || { rm -rf "$REL"; die "uv sync failed; the release was removed"; }
  "$REL/backend/.venv/bin/python" -I -c 'import sys, platform; assert platform.python_version() == sys.argv[1]; print("venv python", platform.python_version())' "$PY_VERSION" \
    || { rm -rf "$REL"; die "the venv of $SHA does not run CPython $PY_VERSION; the release was removed"; }
  ln -sfn "$APP/.env" "$REL/backend/.env"
  printf '%s\n' "$SHA" > "$REL/REVISION"
  chown -R root:kalavigyan "$REL"
  chmod -R go-w "$REL"
  touch "$REL/.complete"
}

prune() {
  local keep=() r n=0
  for r in current slot-8000 slot-8001; do
    if [ -e "$APP/$r" ]; then keep+=("$(readlink -f "$APP/$r")"); fi
  done
  while IFS= read -r r; do
    n=$((n + 1))
    [ "$n" -le "$KEEP" ] && keep+=("$r") && continue
    if printf '%s\n' "${keep[@]}" | grep -qxF "$r"; then continue; fi
    rm -rf "$r"
    say "pruned $r"
  done < <(find "$APP/releases" -mindepth 1 -maxdepth 1 -type d ! -name '.*' -printf '%T@ %p\n' | sort -rn | cut -d' ' -f2-)
}

install_units
/usr/local/sbin/kv-render-env
if [ -f "$REL/.complete" ] && [ "$(readlink -f "$APP/current" 2>/dev/null || true)" = "$(readlink -f "$REL")" ]; then
  say "$SHA is already live; restarting it so it reads the current environment"
  /usr/local/sbin/kv-blue-green restart
else
  build_release
  /usr/local/sbin/kv-blue-green release "$SHA"
  prune
fi
curl -fsS -m 10 -o /dev/null http://127.0.0.1/health || die "nginx does not answer /health after the release"
/usr/local/sbin/kv-blue-green status
rm -f "$TARBALL"
say "release $SHA is live"
