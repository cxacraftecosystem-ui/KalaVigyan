#!/usr/bin/env bash
set -euo pipefail

ORDER="$(dirname "${BASH_SOURCE[0]}")/../../scripts/release_order.sh"

say() { printf '%s\n' "$*"; }
decide() {
  printf 'api=%s\n' "$1" >> "$GITHUB_OUTPUT"
  say "$2"
  exit 0
}

[ -n "${API_BASE_URL:-}" ] || { say "::error::api-base-url is not set, so the build cannot tell which API answers"; exit 1; }
command -v yq > /dev/null || { say "::error::yq is not on the runner; cannot read the Backend checks paths"; exit 1; }
live="$(bash "$ORDER" live)"
[[ "$live" =~ ^[0-9a-f]{40}$ ]] \
  || decide waiting "::warning::the API at $API_BASE_URL names no release commit ('${live:-no answer}'); the web app waits for Deploy backend, which builds it once its release answers"
git fetch --quiet --no-tags --depth=1 origin "+refs/heads/main:refs/remotes/origin/main"
head="$(git rev-parse refs/remotes/origin/main)"
git cat-file -e "$live^{commit}" 2> /dev/null || git fetch --quiet --no-tags --depth=1 origin "$live" 2> /dev/null \
  || decide waiting "::warning::the API runs $live, which this repository does not hold; the web app waits for Deploy backend"
mapfile -t globs < <(yq -r '.on.push.paths[]' .github/workflows/backend-checks.yml)
[ "${#globs[@]}" -gt 0 ] || { say "::error::Backend checks lists no push paths"; exit 1; }
specs=()
for glob in "${globs[@]}"; do specs+=(":(glob)$glob"); done
if git diff --quiet "$live" "$head" -- "${specs[@]}"; then
  decide live "the API runs $live and main ($head) changes nothing the API serves since; the web app builds now"
fi
decide waiting "main ($head) changes the API since $live, the release the API runs; Deploy backend builds the web app once that API answers"
