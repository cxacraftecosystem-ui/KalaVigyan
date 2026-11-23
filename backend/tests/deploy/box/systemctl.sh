#!/usr/bin/env bash
set -u
units="$BOX/units"
verb="${1:-}"
[ "$#" -gt 0 ] && shift
quiet=no
if [ "${1:-}" = --quiet ]; then quiet=yes; shift; fi
unit="${1:-}"
note() { printf '%s\n' "$*" >> "$BOX/events.log"; }
case "$verb" in
  is-active)
    if [ -e "$units/$unit" ]; then
      [ "$quiet" = yes ] || echo active
      exit 0
    fi
    [ "$quiet" = yes ] || echo inactive
    exit 3 ;;
  start|restart)
    note "$verb $unit"
    touch "$units/$unit"
    if [ -e "$BOX/unreachable-database" ]; then touch "$units/$unit.unready"; else rm -f "$units/$unit.unready"; fi ;;
  stop)
    note "stop $unit"
    rm -f "$units/$unit" "$units/$unit.unready" ;;
  *)
    note "$verb $unit" ;;
esac
exit 0
