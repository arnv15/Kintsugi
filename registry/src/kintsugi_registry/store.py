"""The Registry's storage: a directory of `<skill-id>/SKILL.md` folders.

There is no database. The directory of Skill documents *is* the store, which is
what keeps one copy of the truth between what the Registry serves and what an
agent installs (ADR-0002, ADR-0008).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .errors import MalformedSkill
from .skill import Skill

SKILL_FILENAME = "SKILL.md"


@dataclass(frozen=True)
class StoreContents:
    """Everything under the root: the Skills, and what could not be read as one."""

    skills: list[Skill] = field(default_factory=list)
    unreadable: list[str] = field(default_factory=list)


class SkillStore:
    """Reads and writes Skill documents under a single root directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _document_path(self, skill_id: str) -> Path:
        return self.root / skill_id / SKILL_FILENAME

    def exists(self, skill_id: str) -> bool:
        return self._document_path(skill_id).is_file()

    def save(self, skill: Skill) -> Path:
        path = self._document_path(skill.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(skill.render_document(), encoding="utf-8")
        return path

    def load(self, skill_id: str) -> Skill | None:
        path = self._document_path(skill_id)
        if not path.is_file():
            return None
        return Skill.parse_document(skill_id, path.read_text(encoding="utf-8"))

    def load_all(self) -> StoreContents:
        """Every stored Skill, ordered by id so callers see a stable list.

        A document that cannot be read is set aside rather than raised: this
        root is shared and long-lived, and one hand-edited file should not take
        every other Skill down with it. The ids are reported so the breakage is
        visible instead of silent.
        """
        if not self.root.is_dir():
            return StoreContents()

        skills = []
        unreadable = []
        for child in sorted(self.root.iterdir()):
            if not child.is_dir() or not (child / SKILL_FILENAME).is_file():
                continue
            try:
                skill = self.load(child.name)
            except (MalformedSkill, OSError):
                unreadable.append(child.name)
                continue
            if skill is not None:
                skills.append(skill)
        return StoreContents(skills=skills, unreadable=unreadable)

    def clear(self) -> list[str]:
        """Remove every stored Skill and return the ids removed.

        Only entries that resolve to a directory holding `SKILL.md` are removed,
        so a root that a person has pointed at the wrong place loses nothing else.
        A top-level symlink is unlinked without traversing its target.
        """
        if not self.root.is_dir():
            return []

        removed = []
        for child in sorted(self.root.iterdir()):
            if not child.is_dir() or not (child / SKILL_FILENAME).is_file():
                continue
            if child.is_symlink():
                child.unlink()
                removed.append(child.name)
                continue
            _remove_tree(child)
            removed.append(child.name)
        return removed


def _remove_tree(directory: Path) -> None:
    for entry in sorted(directory.iterdir(), reverse=True):
        if entry.is_dir() and not entry.is_symlink():
            _remove_tree(entry)
        else:
            entry.unlink()
    directory.rmdir()
