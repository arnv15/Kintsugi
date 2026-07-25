"""The guard that stops a Skill carrying code out of the repo it was learned in.

ADR-0002 lets a Skill include a short before/after snippet, because the cheapest
way to make a model apply a pattern is to show it one. The cheapest way to
*write* that snippet is to paste the real diff, which would turn the Registry
into a cache of one repo's patches. So a code block over two lines is refused if
it appears, whitespace-normalized, anywhere in the repo the Skill was learned in.

Only fenced blocks are examined. The failure this is built for is an agent
taking the lazy route, and the lazy route writes a fence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MAX_UNCHECKED_BLOCK_LINES = 2
"""Blocks *longer* than this are compared; two lines or fewer are too short to mean anything."""

MAX_SCANNED_FILE_BYTES = 2_000_000

SKIPPED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "dist",
        "build",
        ".idea",
        ".vscode",
    }
)

_FENCED_BLOCK = re.compile(r"^(?P<fence>```+|~~~+)[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$", re.DOTALL | re.MULTILINE)
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Leak:
    """One code block that was found verbatim in the repo."""

    snippet: str
    found_in: str
    """Repo-relative path of the file it collided with."""


def normalize(text: str) -> str:
    """Collapse every run of whitespace to one space, so layout cannot disguise a paste."""
    return _WHITESPACE.sub(" ", text).strip()


def extract_code_blocks(body: str) -> list[str]:
    """Every fenced code block in a Skill body, fences excluded."""
    return [match.group("code") for match in _FENCED_BLOCK.finditer(body)]


def leakable_blocks(body: str) -> list[str]:
    """The code blocks long enough that sharing them with the repo means something."""
    return [
        block
        for block in extract_code_blocks(body)
        if len([line for line in block.splitlines() if line.strip()]) > MAX_UNCHECKED_BLOCK_LINES
    ]


def find_leaks(body: str, repo_path: Path) -> list[Leak]:
    """Code blocks from `body` that appear verbatim somewhere under `repo_path`.

    Each block is reported once, against the first file it collides with — a
    caller needs to know that a snippet must be rewritten, not every place it
    happens to appear.
    """
    blocks = leakable_blocks(body)
    if not blocks:
        return []

    pending = {normalize(block): block for block in blocks}
    leaks = []

    for file_path in _scan_files(repo_path):
        if not pending:
            break
        contents = _read_text(file_path)
        if contents is None:
            continue
        haystack = normalize(contents)
        for needle in [key for key in pending if key in haystack]:
            leaks.append(
                Leak(
                    snippet=pending.pop(needle),
                    found_in=file_path.relative_to(repo_path).as_posix(),
                )
            )

    return leaks


def _scan_files(repo_path: Path) -> list[Path]:
    """Every plausibly-text file under the repo, in a stable order."""
    found = []
    for path in sorted(repo_path.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if SKIPPED_DIRECTORIES.intersection(path.relative_to(repo_path).parts[:-1]):
            continue
        found.append(path)
    return found


def _read_text(path: Path) -> str | None:
    """The file's text, or None if it is too large or is not text at all."""
    try:
        if path.stat().st_size > MAX_SCANNED_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
