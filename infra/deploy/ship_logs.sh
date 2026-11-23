#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
FILES="$HERE/logs"
PIN="$HERE/cloudwatch-agent.pin"
AGENT_HOME=/opt/aws/amazon-cloudwatch-agent
AGENT_CONFIG="$AGENT_HOME/etc/kalavigyan.json"
LOG_DIR=/var/log/kalavigyan
JOURNALD_CONF=/etc/systemd/journald.conf.d/forward.conf
RSYSLOG_CONF=/etc/rsyslog.d/20-kalavigyan.conf
LOGROTATE_CONF=/etc/logrotate.d/kalavigyan
NGINX_CONF=/etc/nginx/conf.d/kalavigyan-logs.conf

say() { printf '%s\n' "$*" >&2; }
die() { say "::error::$*"; exit 1; }
pinned() { sed -n "s/^$1=//p" "$PIN"; }

[ "$(id -u)" = 0 ] || die "run as root"
[ -f "$PIN" ] || die "$PIN is missing; the release does not say which CloudWatch agent ships its logs"
CW_VERSION="$(pinned CW_VERSION)"
CW_URL="$(pinned CW_URL)"
CW_SHA256="$(pinned CW_SHA256)"
[[ "$CW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9a-z]+$ ]] || die "$PIN: CW_VERSION '$CW_VERSION' is not a CloudWatch agent release"
[[ "$CW_URL" == "https://amazoncloudwatch-agent-ap-south-1.s3.ap-south-1.amazonaws.com/ubuntu/amd64/$CW_VERSION/amazon-cloudwatch-agent.deb" ]] || die "$PIN: CW_URL is not the pinned agent's download"
[[ "$CW_SHA256" =~ ^[0-9a-f]{64}$ ]] || die "$PIN: CW_SHA256 is not a sha256"

check_nothing() { :; }
check_rsyslog() { rsyslogd -N1; }
check_logrotate() { logrotate -d "$LOGROTATE_CONF"; }
check_nginx() { nginx -t; }
restart_journald() { systemctl restart systemd-journald; }
restart_rsyslog() { systemctl restart rsyslog; }
reload_nginx() { systemctl reload nginx; }

swap_in() {
  local src="$1" dst="$2" check="$3" apply="$4" prev
  if cmp -s "$src" "$dst"; then return 0; fi
  prev="$(mktemp)"
  if [ -f "$dst" ]; then cp -p "$dst" "$prev"; fi
  install -D -o root -g root -m 0644 "$src" "$dst"
  if ! "$check" >/dev/null 2>&1; then
    if [ -s "$prev" ]; then cp -p "$prev" "$dst"; else rm -f "$dst"; fi
    rm -f "$prev"
    die "$dst was refused by its check; the previous one is back"
  fi
  rm -f "$prev"
  "$apply"
  say "installed $dst"
}

install_agent() {
  local stage
  if [ "$(cat "$AGENT_HOME/bin/CWAGENT_VERSION" 2>/dev/null || true)" = "$CW_VERSION" ]; then return 1; fi
  stage="$(mktemp -d)"
  if ! curl -fsSL --proto '=https' --tlsv1.2 --retry 5 --retry-delay 10 --retry-all-errors --connect-timeout 30 --max-time 900 -o "$stage/agent.deb" "$CW_URL" \
    || ! echo "${CW_SHA256}  $stage/agent.deb" | sha256sum -c - >&2 \
    || ! dpkg -i "$stage/agent.deb" >&2; then
    rm -rf "$stage"
    die "the CloudWatch agent $CW_VERSION could not be installed from $CW_URL; nothing ships until the next release"
  fi
  rm -rf "$stage"
  say "installed the CloudWatch agent $CW_VERSION"
}

route_to_files() {
  if ! command -v rsyslogd >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y rsyslog >&2
  fi
  install -d -o syslog -g adm -m 0750 "$LOG_DIR"
  swap_in "$FILES/journald.conf" "$JOURNALD_CONF" check_nothing restart_journald
  swap_in "$FILES/rsyslog.conf" "$RSYSLOG_CONF" check_rsyslog restart_rsyslog
  swap_in "$FILES/logrotate.conf" "$LOGROTATE_CONF" check_logrotate check_nothing
  swap_in "$FILES/nginx.conf" "$NGINX_CONF" check_nginx reload_nginx
  readable_by_adm "$LOG_DIR"/*.log /var/log/nginx/error.log
}

readable_by_adm() {
  local file
  for file in "$@"; do
    [ -f "$file" ] || continue
    chgrp adm "$file" && chmod g+r "$file"
  done
}

ship() {
  local restart=no
  if install_agent; then restart=yes; fi
  if ! id -nG cwagent | tr ' ' '\n' | grep -qx adm; then
    usermod -aG adm cwagent
    restart=yes
  fi
  if ! cmp -s "$FILES/cloudwatch-agent.json" "$AGENT_CONFIG"; then
    install -o root -g root -m 0644 "$FILES/cloudwatch-agent.json" "$AGENT_CONFIG"
    restart=yes
  fi
  systemctl is-active --quiet amazon-cloudwatch-agent || restart=yes
  if [ "$restart" = yes ]; then
    "$AGENT_HOME/bin/amazon-cloudwatch-agent-ctl" -a fetch-config -m ec2 -s -c "file:$AGENT_CONFIG" >&2
    systemctl restart amazon-cloudwatch-agent
  fi
}

route_to_files
ship
say "the box ships kv-api, kv-worker, kv-fetcher, kv-contributions and nginx to CloudWatch Logs"
