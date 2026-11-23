#!/usr/bin/env bash
if [ "$LIVE_RELEASE" = unreachable ]; then exit 7; fi
printf '{"status": "ok", "release": "%s", "version": "1"}\n' "$LIVE_RELEASE"
