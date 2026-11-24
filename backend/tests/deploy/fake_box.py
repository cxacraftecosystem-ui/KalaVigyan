import os
import re
import shutil
import stat
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SWITCH = REPO / "infra" / "deploy" / "blue_green.sh"
STUBS = Path(__file__).resolve().parent / "box"
COMMANDS = {
    "systemctl": "systemctl.sh",
    "curl": "curl.sh",
    "runuser": "runuser.sh",
    "id": "id.sh",
    "install": "install.sh",
    "nginx": "quiet.sh",
    "journalctl": "quiet.sh",
    "sleep": "quiet.sh",
}
PREVIOUS, LIVE, NEW = "a" * 40, "b" * 40, "c" * 40
WORKERS = ("kv-worker", "kv-fetcher", "kv-contributions")
SITE = "server {\n    location / {\n        proxy_pass http://127.0.0.1:8000;\n    }\n}\n"
PROXIED = re.compile(r"proxy_pass http://127\.0\.0\.1:(\d+);")
RUN_LIMIT = 90


@dataclass(frozen=True)
class Run:
    code: int
    said: str
    seconds: float


def executable(source: Path, target: Path) -> None:
    shutil.copyfile(source, target)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class FakeBox:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.app = root / "app"
        self.units = root / "units"
        self.units.mkdir()
        for sha in (PREVIOUS, LIVE, NEW):
            self._build(sha)
        for sha in (PREVIOUS, LIVE):
            (self.app / "releases" / sha / ".released").touch()
        self.link("slot-8000", LIVE)
        self.link("slot-8001", PREVIOUS)
        self.link("current", LIVE)
        (root / "site.conf").write_text(SITE, encoding="utf-8")
        (root / "app.env").write_text("APP_ENV='test'\n", encoding="utf-8")
        (root / "events.log").touch()
        (root / "runs.log").touch()
        for unit in ("kv-api@8000", *WORKERS):
            (self.units / unit).touch()
        self._commands()

    def _build(self, sha: str) -> None:
        backend = self.app / "releases" / sha / "backend"
        (backend / ".venv" / "bin").mkdir(parents=True)
        (backend / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")
        executable(STUBS / "python.sh", backend / ".venv" / "bin" / "python")

    def _commands(self) -> None:
        commands = self.root / "bin"
        commands.mkdir()
        for name, stub in COMMANDS.items():
            executable(STUBS / stub, commands / name)

    def link(self, name: str, sha: str) -> None:
        path = self.app / name
        if path.is_symlink():
            path.unlink()
        path.symlink_to(self.app / "releases" / sha)

    def mark(self, name: str, value: str = "") -> None:
        (self.root / name).write_text(value, encoding="utf-8")

    def slot(self, name: str) -> str:
        return Path(os.readlink(self.app / name)).name

    def proxied(self) -> str:
        found = PROXIED.search((self.root / "site.conf").read_text(encoding="utf-8"))
        assert found is not None
        return found.group(1)

    def active(self, unit: str) -> bool:
        return (self.units / unit).exists()

    def events(self) -> list[str]:
        return (self.root / "events.log").read_text(encoding="utf-8").splitlines()

    def runs(self, module: str) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        for line in (self.root / "runs.log").read_text(encoding="utf-8").splitlines():
            name, ran_from, served_by = line.split()
            if name == module:
                found.append((ran_from, served_by))
        return found

    def run(self, *arguments: str) -> Run:
        env = {
            **os.environ,
            "PATH": f"{self.root / 'bin'}{os.pathsep}{os.environ['PATH']}",
            "APP": str(self.app),
            "NGINX_SITE": str(self.root / "site.conf"),
            "ENV_FILE": str(self.root / "app.env"),
            "STATE_DIR": str(self.root / "state"),
            "BOX": str(self.root),
            "REAL_SLEEP": shutil.which("sleep") or "sleep",
            "HEALTH_LIMIT": "2",
            "DRAIN": "0",
            "NGINX_SWITCH_SECONDS": "1",
            "CLEANUP_SECONDS": "10",
        }
        said = self.root / "said.txt"
        started = time.monotonic()
        with said.open("w", encoding="utf-8") as out:
            done = subprocess.run(
                ["bash", str(SWITCH), *arguments],
                env=env,
                stdout=out,
                stderr=out,
                timeout=RUN_LIMIT,
                check=False,
            )
        return Run(done.returncode, said.read_text(encoding="utf-8"), time.monotonic() - started)
