import io
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIPPED_PATHS = ["Dockerfile", ".dockerignore", "requirements.txt", "LICENSE", "backend", "frontend"]
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".ico"}
SPACE_URL = "https://huggingface.co/spaces/{space}"
SPACE_README = """---
title: Drawlab
emoji: ✏️
colorFrom: blue
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: The AI that doesn't generate. It draws.
---

# Drawlab

Drop an image: a team of Meta AI agents redraws it as a clean, layered SVG, stroke by stroke.

Source code and documentation: {repository}
"""


def git(*arguments: str, cwd: Path = ROOT) -> bytes:
    return subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True).stdout


def warn_if_dirty() -> None:
    if git("status", "--porcelain").strip():
        print("Warning: uncommitted changes are not deployed, only the last commit is.")


def extract_commit(target: Path) -> int:
    archive = tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", "HEAD", *SHIPPED_PATHS)))
    shipped = [member for member in archive.getmembers() if Path(member.name).suffix.lower() not in BINARY_SUFFIXES]
    archive.extractall(target, members=shipped, filter="data")
    return sum(1 for member in shipped if member.isfile())


def write_readme(target: Path) -> None:
    repository = git("remote", "get-url", "origin").decode().strip().removesuffix(".git")
    (target / "README.md").write_text(SPACE_README.format(repository=repository), encoding="utf-8")


def push(target: Path, space: str) -> None:
    commit = git("rev-parse", "--short", "HEAD").decode().strip()
    git("init", "--initial-branch=main", cwd=target)
    git("add", "--all", cwd=target)
    git("commit", "--message", f"Deploy {commit}", cwd=target)
    subprocess.run(["git", "push", "--force", SPACE_URL.format(space=space), "main"], cwd=target, check=True)


def main(space: str) -> None:
    warn_if_dirty()
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder)
        count = extract_commit(target)
        write_readme(target)
        print(f"Deploying {count} files to {SPACE_URL.format(space=space)}")
        push(target, space)
    print(f"Done. Follow the build at {SPACE_URL.format(space=space)}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or "/" not in sys.argv[1]:
        sys.exit("usage: python scripts/deploy_space.py <hugging-face-user>/<space-name>")
    main(sys.argv[1])
