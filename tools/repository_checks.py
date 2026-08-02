from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".in",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    ".python-version",
}
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def git_files(*arguments: str) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", *arguments, "-z"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    return [
        PROJECT_ROOT / entry.decode("utf-8")
        for entry in result.stdout.split(b"\0")
        if entry
    ]


def is_text_file(path: Path) -> bool:
    return path.suffix.casefold() in TEXT_SUFFIXES or path.name in TEXT_NAMES


def check_text_file(path: Path, *, enforce_whitespace: bool) -> tuple[str, list[str]]:
    relative = path.relative_to(PROJECT_ROOT).as_posix()
    problems: list[str] = []
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return "", [f"{relative}: not valid UTF-8 ({exc})"]

    if enforce_whitespace and data and not data.endswith(b"\n"):
        problems.append(f"{relative}: missing final newline")

    if enforce_whitespace and path.suffix.casefold() != ".md":
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.endswith((" ", "\t")):
                problems.append(f"{relative}:{line_number}: trailing whitespace")

    return text, problems


def check_markdown_links(path: Path, text: str) -> list[str]:
    relative = path.relative_to(PROJECT_ROOT).as_posix()
    problems: list[str] = []
    for match in MARKDOWN_LINK.finditer(text):
        target = match.group(1).strip().strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        path_part = unquote(target.split("#", 1)[0])
        if not path_part:
            continue
        destination = (path.parent / path_part).resolve()
        if not destination.exists():
            problems.append(f"{relative}: broken local link: {target}")
    return problems


def main() -> int:
    problems: list[str] = []
    untracked_files = set(git_files("--others", "--exclude-standard"))
    repository_files = git_files("--cached", "--others", "--exclude-standard")
    for path in repository_files:
        if not path.is_file() or not is_text_file(path):
            continue
        text, text_problems = check_text_file(
            path,
            enforce_whitespace=path in untracked_files,
        )
        problems.extend(text_problems)
        if path.suffix.casefold() == ".md" and text:
            problems.extend(check_markdown_links(path, text))

    if problems:
        print("Repository checks failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1

    print("Repository text files are UTF-8 and local Markdown links resolve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
