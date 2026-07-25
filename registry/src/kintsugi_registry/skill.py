"""The Skill document: a Claude Code `SKILL.md` with YAML frontmatter.

Per ADR-0002 a Skill *is* a `SKILL.md` file, so this module owns the only
mapping between the in-memory Skill and the bytes on disk. Callers hand the
Registry structured fields and get a well-formed document back; they never
assemble frontmatter themselves, so a Skill cannot be stored with malformed
YAML or with `aliases` that are a string instead of a list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

from .errors import MalformedSkill

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)
_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Derive a Skill id from its name. Empty results are rejected upstream."""
    return _NON_SLUG.sub("-", name.strip().lower()).strip("-")


@dataclass(frozen=True)
class Skill:
    """One Root Cause Class and how bugs of that class are fixed."""

    id: str
    name: str
    description: str
    aliases: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    published_by: str = "unknown"
    body: str = ""

    def render_document(self) -> str:
        """Serialize to the `SKILL.md` text that gets written to disk.

        The result is installable as-is: an agent on the Reuse Path writes it
        into `.claude/skills/<id>/SKILL.md` and Claude Code loads it natively.
        """
        frontmatter = {
            "name": self.name,
            "description": self.description,
            "aliases": list(self.aliases),
            "sources": list(self.sources),
            "published_by": self.published_by,
        }
        rendered = yaml.safe_dump(
            frontmatter,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=10_000,
        )
        body = self.body if self.body.endswith("\n") or not self.body else self.body + "\n"
        return f"---\n{rendered}---\n\n{body}"

    @classmethod
    def parse_document(cls, skill_id: str, text: str) -> Skill:
        """Read a `SKILL.md` back into a Skill."""
        match = _FRONTMATTER.match(text)
        if match is None:
            raise MalformedSkill(f"Skill '{skill_id}' has no YAML frontmatter block.")

        try:
            loaded = yaml.safe_load(match.group(1))
        except yaml.YAMLError as exc:
            raise MalformedSkill(f"Skill '{skill_id}' has unparseable frontmatter: {exc}") from exc

        if not isinstance(loaded, dict):
            raise MalformedSkill(f"Skill '{skill_id}' frontmatter is not a mapping.")

        name = loaded.get("name")
        description = loaded.get("description")
        if not isinstance(name, str) or not isinstance(description, str):
            raise MalformedSkill(
                f"Skill '{skill_id}' frontmatter needs string 'name' and 'description' fields."
            )

        return cls(
            id=skill_id,
            name=name,
            description=description,
            aliases=_as_str_list(loaded.get("aliases")),
            sources=_as_str_list(loaded.get("sources")),
            published_by=str(loaded.get("published_by", "unknown")),
            body=match.group(2).lstrip("\n"),
        )


def _as_str_list(value: object) -> list[str]:
    """Coerce a frontmatter field to a list of strings, tolerating a bare string."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
