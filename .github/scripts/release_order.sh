#!/usr/bin/env bash
set -euo pipefail

COMMIT='^[0-9a-f]{40}$'
ROLLBACK="sudo kv-blue-green rollback <release> on the box (docs/RUNBOOK.md, Roll back)"

say() { printf '%s\n' "$*"; }
note() { say "$*" >&2; }
warn() { say "::warning::$*" >&2; }
fail() { say "::error::$*" >&2; exit 1; }
api() { say "${API_BASE_URL:-the API (API_BASE_URL is not set)}"; }

live() {
  [ -n "${API_BASE_URL:-}" ] || return 0
  curl -fsS -m 20 --retry 3 --retry-all-errors "$API_BASE_URL/health" | jq -r '.release // empty' || true
}

held() {
  git cat-file -e "$1^{commit}" 2> /dev/null || git fetch --quiet --no-tags origin "$1" 2> /dev/null
}

descends() {
  local commit="$1" serving
  [[ "$commit" =~ $COMMIT ]] || fail "descends needs a full commit id, not '$commit'"
  serving="$(live)"
  if ! [[ "$serving" =~ $COMMIT ]]; then
    warn "$(api) names no release commit ('${serving:-no answer}'), so nothing shows which release $commit follows; the deploy goes on"
    return 0
  fi
  if [ "$serving" = "$commit" ]; then
    note "production serves $commit already; the deploy starts it again on the environment as it is now"
    return 0
  fi
  held "$serving" || fail "production serves $serving, which this repository does not hold, so nothing shows that $commit comes after it. To serve another release, run $ROLLBACK"
  if git merge-base --is-ancestor "$serving" "$commit"; then
    note "$commit comes after $serving, the release production serves"
    return 0
  fi
  fail "$commit does not come after $serving, the release production serves; a deploy never moves production back or sideways. To go back to an older release, run $ROLLBACK"
}

resolved() {
  local ref="$1" found
  if [[ "$ref" =~ $COMMIT ]]; then
    say "$ref"
    return 0
  fi
  found="$(git ls-remote --exit-code origin "refs/heads/$ref" | cut -f1)" || fail "origin has no branch '$ref' to read as the release before"
  say "$found"
}

before() {
  local base serving
  base="$(resolved "$1")"
  serving="$(live)"
  if [[ "$serving" =~ $COMMIT ]]; then
    say "$serving"
  else
    warn "$(api) names no release commit ('${serving:-no answer}'); only $base is read as the release before"
  fi
  [ "$serving" = "$base" ] || say "$base"
}

case "${1:-}" in
  live) live ;;
  descends) descends "${2:-}" ;;
  before)
    [ -n "${2:-}" ] || fail "before needs the branch or commit the change was made on"
    before "$2" ;;
  *) fail "usage: release_order.sh live | descends <commit> | before <branch or commit>" ;;
esac
