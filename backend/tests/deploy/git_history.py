import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .fake_box import executable

STUBS = Path(__file__).resolve().parent / "gate"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "Gate test",
    "GIT_AUTHOR_EMAIL": "gate@example.org",
    "GIT_COMMITTER_NAME": "Gate test",
    "GIT_COMMITTER_EMAIL": "gate@example.org",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


@dataclass(frozen=True)
class History:
    root: Path
    work: Path
    origin: str
    checkout: Path
    first: str
    api: str
    web: str


def git(cwd: Path, *arguments: str) -> str:
    done = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        env={**os.environ, **GIT_ENV},
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def committed(work: Path, files: dict[str, str]) -> str:
    for name, text in files.items():
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_text(text, encoding="utf-8")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", ", ".join(files))
    return git(work, "rev-parse", "HEAD")


def made_history(root: Path) -> History:
    origin = f"file://{root / 'origin.git'}"
    git(root, "init", "-q", "--bare", "-b", "main", "origin.git")
    work = root / "work"
    git(root, "init", "-q", "-b", "main", "work")
    first = committed(
        work,
        {
            ".github/workflows/backend-checks.yml": "name: Backend checks\n",
            "backend/app/routes.py": "ROUTES = ('/api/crafts',)\n",
            "frontend/app/page.tsx": "export const calls = '/api/crafts';\n",
        },
    )
    api = committed(
        work,
        {
            "backend/app/routes.py": "ROUTES = ('/api/crafts', '/api/kilns')\n",
            "frontend/app/page.tsx": "export const calls = '/api/kilns';\n",
        },
    )
    web = committed(work, {"frontend/app/footer.tsx": "export const year = 2026;\n"})
    git(work, "push", "-q", origin, "main")
    git(root, "clone", "-q", origin, "checkout")
    commands = root / "bin"
    commands.mkdir()
    for name in ("curl", "yq"):
        executable(STUBS / f"{name}.sh", commands / name)
    return History(root, work, origin, root / "checkout", first, api, web)
