import re
from pathlib import Path

from app.services.served_pages import BUILD_READ_SECONDS

REPO = Path(__file__).resolve().parents[2]
SWITCH = REPO / "infra" / "deploy" / "blue_green.sh"


def shell_function(name: str) -> str:
    source = SWITCH.read_text(encoding="utf-8")
    found = re.search(rf"^{name}\(\) \{{\n(.*?)^\}}$", source, re.MULTILINE | re.DOTALL)
    assert found is not None, name
    return found.group(1)


def called_in_order(body: str, *calls: str) -> bool:
    places = [body.find(call) for call in calls]
    return all(place >= 0 for place in places) and places == sorted(places)


def test_a_release_rebuilds_pages_before_it_goes_live_and_refreshes_the_web_after() -> None:
    assert called_in_order(shell_function("seed"), "app.scripts.import_curation", 'rebuild_pages "$tree"')
    assert "app.scripts.rebuild_stale_pages" in shell_function("rebuild_pages")
    release = shell_function("cmd_release")
    assert called_in_order(release, 'seed "$tree"', "start_and_promote", 'refresh_served_pages "$tree"')
    assert called_in_order(shell_function("cmd_rollback"), "start_and_promote", "refresh_served_pages")
    refresh = shell_function("refresh_served_pages")
    assert "app.scripts.refresh_served_pages --state '$STATE/served-pages.json'" in refresh


def test_the_web_build_starts_only_after_the_release_has_refreshed_the_pages() -> None:
    workflow = (REPO / ".github" / "workflows" / "deploy-backend.yml").read_text(encoding="utf-8")
    names = re.findall(r"^      - name: (.+)$", workflow, re.MULTILINE)
    release = names.index("Release on the box (blue/green through SSM)")
    build = names.index("Build the web app now that the API is live")
    assert release < build == len(names) - 1


def test_a_build_time_read_waits_as_long_as_the_slowest_document_the_release_warns_about() -> None:
    source = (REPO / "frontend" / "lib" / "server" / "readingPages.ts").read_text(encoding="utf-8")
    found = re.search(r"export const STATIC_FETCH_TIMEOUT_MS = ([\d_]+);", source)
    assert found is not None
    assert int(found.group(1).replace("_", "")) == BUILD_READ_SECONDS * 1000 == 30_000
