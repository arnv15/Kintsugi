"""Operator commands for the Skill Registry.

These are for the person running a rehearsal, not for an agent — clearing the
shared Registry is deliberately absent from the MCP tool surface, so it lives
here instead.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .config import SKILLS_DIR_ENV_VAR, resolve_skills_dir
from .registry import SkillRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kintsugi-registry-admin",
        description="Inspect and reset the Kintsugi Skill Registry.",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--skills-dir",
        default=None,
        help=f"Skill directory to act on (default: ${SKILLS_DIR_ENV_VAR}, "
        "else ~/.kintsugi/skills).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser(
        "list", parents=[common], help="List the Skills currently in the Registry."
    )

    clear = commands.add_parser(
        "clear",
        parents=[common],
        help="Remove every Skill, so the next Run takes the Research Path again.",
    )
    clear.add_argument("--yes", action="store_true", help="Actually remove the Skills.")
    clear.add_argument(
        "--dry-run", action="store_true", help="Print what would be removed and stop."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    skills_dir = resolve_skills_dir(args.skills_dir)
    registry = SkillRegistry(skills_dir=skills_dir)

    if args.command == "list":
        return _list(registry, str(skills_dir))
    return _clear(registry, str(skills_dir), confirmed=args.yes, dry_run=args.dry_run)


def _list(registry: SkillRegistry, skills_dir: str) -> int:
    listed = registry.list_skills()
    print(f"{listed['count']} Skill(s) in {skills_dir}")
    for entry in listed["skills"]:
        print(f"  {entry['id']}  —  {entry['name']}")

    unreadable = listed["unreadable"]
    if unreadable:
        print(
            f"\n{len(unreadable)} unreadable document(s) — skipped by search, so a Skill you "
            "expect to match will not:",
            file=sys.stderr,
        )
        for skill_id in unreadable:
            print(f"  {skill_id}", file=sys.stderr)
    return 0


def _clear(registry: SkillRegistry, skills_dir: str, *, confirmed: bool, dry_run: bool) -> int:
    present = [entry["id"] for entry in registry.list_skills()["skills"]]

    if dry_run:
        print(f"Would remove {len(present)} Skill(s) from {skills_dir}:")
        for skill_id in present:
            print(f"  {skill_id}")
        return 0

    if present and not confirmed:
        print(
            f"Refusing to remove {len(present)} Skill(s) from {skills_dir} without --yes. "
            "Re-run with --yes to clear, or --dry-run to see what would go.",
            file=sys.stderr,
        )
        return 2

    removed = registry.clear()
    print(f"Removed {len(removed)} Skill(s) from {skills_dir}")
    for skill_id in removed:
        print(f"  {skill_id}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
