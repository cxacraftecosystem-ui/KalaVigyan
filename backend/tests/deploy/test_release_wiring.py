import re
from pathlib import Path

from .fake_box import REPO, SWITCH

DEPLOY = REPO / "infra" / "deploy"
RELEASE = DEPLOY / "release.sh"
UNITS = DEPLOY / "units"
BOX = REPO / "infra" / "terraform" / "user_data.sh"
WORKFLOW = REPO / ".github" / "workflows" / "deploy-backend.yml"
APP_ENV_FILE = "/opt/kalavigyan/.env"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def number(pattern: str, text: str) -> int:
    found = re.search(pattern, text, re.MULTILINE)
    assert found is not None, pattern
    return int(found.group(1))


def service(path: Path) -> dict[str, list[str]]:
    section = read(path).split("[Service]\n", 1)[1].split("\n[", 1)[0]
    settings: dict[str, list[str]] = {}
    for line in section.splitlines():
        key, equals, value = line.partition("=")
        if equals:
            settings.setdefault(key, []).append(value)
    return settings


def test_the_release_stops_itself_and_cleans_up_before_ssm_would_kill_it() -> None:
    workflow, release, switch = read(WORKFLOW), read(RELEASE), read(SWITCH)
    ssm = number(r'^      RELEASE_SECONDS: "(\d+)"$', workflow)
    assert ssm == 2700 == number(r'^SSM_SECONDS="\$\{SSM_SECONDS:-(\d+)\}"$', release)
    assert "--arg t \"$RELEASE_SECONDS\" '{commands: [$s], executionTimeout: [$t]}'" in workflow
    assert 'SSM_SECONDS=$RELEASE_SECONDS bash "\\$work/infra/deploy/release.sh"' in workflow
    margin = number(r"^CLEANUP_MARGIN=(\d+)$", release)
    kill_after = number(r'^CLEANUP_SECONDS="\$\{CLEANUP_SECONDS:-(\d+)\}"$', switch)
    assert (margin, kill_after) == (300, 240) and kill_after < margin
    assert 'kv-blue-green release "$SHA" --within "$left"' in release
    assert 'exec timeout --signal=TERM --kill-after="$CLEANUP_SECONDS" "$seconds"' in switch


def test_a_release_counts_as_live_only_once_the_api_reaches_its_database_and_names_it() -> None:
    switch, release, workflow = read(SWITCH), read(RELEASE), read(WORKFLOW)
    assert "\nREADY=/health/ready\n" in switch
    assert 'wait_answering "$cand" "$READY"' in switch
    assert "http://127.0.0.1/health/ready" in release
    assert '"$API_BASE_URL/health/ready"' in workflow
    assert '[ "$code" = 200 ] && [ "$release" = "$SHA" ]' in workflow


def test_each_api_colour_names_the_release_its_slot_holds() -> None:
    api = service(UNITS / "kv-api@.service")
    assert api["EnvironmentFile"] == [APP_ENV_FILE, "-/opt/kalavigyan/slot-%i/release.env"]
    release = read(RELEASE)
    assert 'printf \'RELEASE=%s\\n\' "$SHA" > "$REL/release.env"' in release
    assert "name_release\n  /usr/local/sbin/kv-blue-green restart" in release
    assert "build_release\n  name_release\n  switch_within_time" in release


def test_the_fetcher_runs_as_a_user_of_its_own_that_sees_no_other_user_s_processes() -> None:
    holders = [
        path for path in UNITS.glob("*.service") if APP_ENV_FILE in service(path).get("EnvironmentFile", [])
    ]
    assert sorted(path.name for path in holders) == [
        "kv-api@.service",
        "kv-contributions.service",
        "kv-worker.service",
    ]
    assert {user for path in holders for user in service(path)["User"]} == {"kalavigyan"}
    fetcher = service(UNITS / "kv-fetcher.service")
    assert (fetcher["DynamicUser"], fetcher["ProtectProc"]) == (["yes"], ["invisible"])
    for shared in ("User", "Group", "SupplementaryGroups"):
        assert shared not in fetcher, shared
    assert fetcher["EnvironmentFile"] == ["/opt/kalavigyan/fetcher.env"]
    assert "-/opt/kalavigyan/.env" in fetcher["InaccessiblePaths"][0].split()


def test_the_code_the_fetcher_runs_stays_readable_to_a_user_outside_the_app_s_group() -> None:
    assert 'install -d -o root -g kalavigyan -m 0755 "$APP" "$APP/releases"' in read(BOX)
    release = read(RELEASE)
    assert 'install -d -o root -g kalavigyan -m 0755 "$REL"' in release
    assert 'chmod -R go-w "$REL"' in release
    assert "install -d -o root -g root -m 0755 /opt/cpython" in release
    assert not re.search(r"chmod -R [a-z]*o[a-z]*-[a-z]*r", release)
