"""Infer a semantic version bump and update VERSION and RELEASE_NOTES.md."""

from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def parse_version() -> tuple[int, int, int]:
    value = (ROOT / "VERSION").read_text().strip()
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError(f"VERSION must be MAJOR.MINOR.PATCH, got {value!r}")
    return tuple(map(int, match.groups()))


def commits(before: str | None, after: str) -> list[tuple[str, str, str, str]]:
    revision = f"{before}..{after}" if before and before != "0" * 40 else after
    output = git("log", "--format=%H%x1f%an%x1f%ae%x1f%s%x1e", revision)
    rows = []
    for row in output.strip("\x1e").split("\x1e"):
        if row:
            rows.append(tuple(row.split("\x1f", 3)))
    return rows


def bump_level(rows: list[tuple[str, str, str, str]]) -> str:
    level = "patch"
    for sha, author, email, subject in rows:
        body = git("show", "-s", "--format=%B", sha)
        if "BREAKING CHANGE:" in body or re.match(r"^[a-z]+!:", subject):
            return "major"
        if re.match(r"^feat(?:ure)?(?:\([^)]*\))?:", subject):
            level = "minor"
    return level


def main() -> None:
    before = os.environ.get("RELEASE_BEFORE")
    after = os.environ.get("RELEASE_AFTER") or git("rev-parse", "HEAD")
    if not before:
        try:
            before = git("rev-parse", f"{after}^")
        except subprocess.CalledProcessError:
            before = None
    rows = commits(before, after)
    if not rows:
        print("No commits found; release unchanged.")
        return
    if any(subject.startswith("chore(release):") for _, _, _, subject in rows):
        print("Release commit already included; release unchanged.")
        return

    major, minor, patch = parse_version()
    level = bump_level(rows)
    if level == "major":
        major, minor, patch = major + 1, 0, 0
    elif level == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    version = f"{major}.{minor}.{patch}"
    (ROOT / "VERSION").write_text(version + "\n")
    date = dt.date.today().isoformat()
    lines = [f"\n## {version} - {date}\n", f"Release type: **{level}**.\n"]
    for sha, author, email, subject in rows:
        lines.append(f"- {subject} — {author} ({email}), `{sha[:7]}`\n")
    notes = ROOT / "RELEASE_NOTES.md"
    notes.write_text(notes.read_text() + "\n".join(lines))
    print(f"version={version}")
    print(f"bump={level}")


if __name__ == "__main__":
    main()
