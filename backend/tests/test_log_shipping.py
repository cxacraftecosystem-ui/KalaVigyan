import json
import re
from pathlib import Path
from typing import Any

from fastapi.routing import iter_route_contexts

from app.main import create_app

REPO = Path(__file__).resolve().parents[2]
DEPLOY = REPO / "infra" / "deploy"
LOGS = DEPLOY / "logs"
TERRAFORM = REPO / "infra" / "terraform"
PIN = DEPLOY / "cloudwatch-agent.pin"
BOX = TERRAFORM / "user_data.sh"
WORKFLOW = REPO / ".github" / "workflows" / "deploy-backend.yml"
SERVICES = ("kv-api", "kv-worker", "kv-fetcher", "kv-contributions")
UNITS = {"kv-api": "kv-api@.service"} | {name: f"{name}.service" for name in SERVICES[1:]}
LINK_TOKEN = "Qx7_r2-LmP9sTu4VwXy8Za1Bc3De5Fg6"
PIN_KEYS = ("CW_VERSION", "CW_URL", "CW_SHA256")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def pinned() -> dict[str, str]:
    rows = (line.partition("=") for line in read(PIN).splitlines())
    return {key: value for key, _, value in rows}


def agent_files() -> list[dict[str, Any]]:
    config = json.loads(read(LOGS / "cloudwatch-agent.json"))
    return config["logs"]["logs_collected"]["files"]["collect_list"]


def token_paths() -> list[str]:
    templates = {route.path for route in iter_route_contexts(create_app().routes) if "{token}" in route.path}
    assert templates, "the app serves no capability-token route"
    return [re.sub(r"\{[^}]+\}", "csl", path.replace("{token}", LINK_TOKEN)) for path in sorted(templates)]


def nginx_logged(path: str) -> str:
    found = re.search(r'"~(.+?)" "(.+?)";', read(LOGS / "nginx.conf"))
    assert found is not None
    pattern = found.group(1).replace("(?<", "(?P<")
    value = re.sub(r"\$\{(\w+)\}", r"\\g<\1>", found.group(2))
    return re.sub(pattern, value, path) if re.match(pattern, path) else path


def test_a_new_box_installs_the_agent_the_release_pins_over_https_with_its_checksum() -> None:
    pin = pinned()
    assert tuple(pin) == PIN_KEYS
    assert pin["CW_URL"] == (
        "https://amazoncloudwatch-agent-ap-south-1.s3.ap-south-1.amazonaws.com/ubuntu/amd64/"
        f"{pin['CW_VERSION']}/amazon-cloudwatch-agent.deb"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", pin["CW_SHA256"])
    box = dict(re.findall(r'^(CW_[A-Z0-9]+)="([^"]*)"$', read(BOX), re.MULTILINE))
    assert box == pin
    assert 'echo "${CW_SHA256}  $t/agent.deb" | sha256sum -c -' in read(BOX)
    assert "sha256sum -c -" in read(DEPLOY / "ship_logs.sh")


def test_each_service_is_named_in_the_journal_routed_to_its_own_file_and_shipped_to_its_own_group() -> None:
    for name, unit in UNITS.items():
        assert f"SyslogIdentifier={name}\n" in read(DEPLOY / "units" / unit), unit
    routed = re.findall(r'\$programname == "([^"]+)"', read(LOGS / "rsyslog.conf"))
    assert tuple(routed) == SERVICES
    assert "/var/log/kalavigyan/%programname%.log" in read(LOGS / "rsyslog.conf")
    shipped = {item["file_path"]: item["log_group_name"] for item in agent_files()}
    assert {
        f"/var/log/kalavigyan/{name}.log": f"/kalavigyan/{name}" for name in SERVICES
    }.items() <= shipped.items()
    assert shipped["/var/log/nginx/kalavigyan-access.log"] == "/kalavigyan/nginx-access"
    assert shipped["/var/log/nginx/error.log"] == "/kalavigyan/nginx-error"


def test_terraform_makes_exactly_the_agent_s_groups_kept_thirty_days_and_the_box_may_write_them() -> None:
    logs = read(TERRAFORM / "logs.tf")
    listed = re.search(r"box_log_streams = \[(.*?)\]", logs)
    assert listed is not None
    groups = {f"/kalavigyan/{name}" for name in re.findall(r'"([^"]+)"', listed.group(1))}
    assert groups == {item["log_group_name"] for item in agent_files()}
    assert re.search(
        r'variable "log_retention_days" \{[^}]*default\s+= 30\n', read(TERRAFORM / "variables.tf")
    )
    assert re.search(r'name\s+= "/\$\{var\.project\}/\$\{each\.key\}"', logs)
    assert "role = aws_iam_role.box.id" in logs
    for action in ("logs:CreateLogStream", "logs:PutLogEvents"):
        assert f'"{action}"' in logs


def test_the_nginx_access_log_masks_every_capability_token_and_keeps_other_paths() -> None:
    for path in token_paths():
        logged = nginx_logged(path)
        assert LINK_TOKEN not in logged, path
        assert "[redacted]" in logged, path
    assert nginx_logged("/api/crafts/Kutch-Ajrakh/page") == "/api/crafts/Kutch-Ajrakh/page"
    assert nginx_logged("/api/upload-links/abc/picture") == "/api/upload-links/[redacted]/picture"


def test_the_shipped_nginx_lines_carry_no_query_string_address_referrer_or_body() -> None:
    form = re.search(r"log_format kalavigyan escape=json '(.+)';", read(LOGS / "nginx.conf"))
    assert form is not None
    assert "$kv_logged_path" in form.group(1)
    for leak in (
        '$request"',
        "$request_uri",
        "$args",
        "$query_string",
        "$remote_addr",
        "$http_referer",
        "$http_x_forwarded_for",
        "$request_body",
        "$http_authorization",
        "$http_cookie",
    ):
        assert leak not in form.group(1), leak
    [errors] = [item for item in agent_files() if item["file_path"] == "/var/log/nginx/error.log"]
    [dropped] = errors["filters"]
    assert dropped["type"] == "exclude"
    for path in token_paths():
        assert re.search(dropped["expression"], f'request: "GET {path} HTTP/1.1"'), path


def test_every_release_installs_the_log_files_after_the_environment_and_before_the_switch() -> None:
    release = read(DEPLOY / "release.sh")
    steps = (
        "\n/usr/local/sbin/kv-render-env\n",
        'bash "$HERE/ship_logs.sh"',
        "build_release\n  name_release\n",
    )
    order = [release.index(step) for step in steps]
    assert order == sorted(order)
    script = read(DEPLOY / "ship_logs.sh")
    for name in sorted(path.name for path in LOGS.iterdir()):
        assert f'"$FILES/{name}"' in script, name
    assert "infra/deploy/ship_logs.sh" in read(WORKFLOW)
