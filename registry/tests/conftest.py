"""Shared fixtures for Skill Registry tests.

Tests work at the Registry's tool boundary — the same four operations exposed
over MCP (`search_skills`, `get_skill`, `publish_skill`, `list_skills`) — and
assert on nothing about how the matcher works.

Two places reach past that boundary on purpose, each noted where it happens:
the ordering proof for the hypothesis guard, which is a claim about sequence
rather than about output, and the safety test for `clear`, which has to look at
the directory because deleting from it is the behaviour under test.
"""

import os
from pathlib import Path

import pytest

from kintsugi_registry.config import SANDBOX_REPO_ENV_VAR, SKILLS_DIR_ENV_VAR
from kintsugi_registry.registry import SkillRegistry

MUTABLE_DEFAULT_SKILL = {
    "name": "Mutable default argument",
    "description": (
        "A mutable object is used as a default parameter value, so the same "
        "object is shared across every call to the function"
    ),
    "aliases": [
        "default argument keeps values from a previous call",
        "shared mutable state between invocations of a function",
        "empty list default parameter accumulates entries",
    ],
    "body": (
        "Bind the default to a sentinel and build the mutable object inside the "
        "function body, so each call gets its own object.\n"
    ),
    "sources": ["https://docs.python.org/3/reference/compound_stmts.html#function-definitions"],
    "published_by": "kintsugi-agent",
}


FLOAT_EQUALITY_SKILL = {
    "name": "Exact equality comparison of floating point numbers",
    "description": (
        "Two floating point numbers are compared with exact equality, so values that "
        "are equal in arithmetic compare unequal because of representation error"
    ),
    "aliases": [
        "decimal arithmetic gives a slightly wrong total",
        "sum of fractions does not equal the expected number",
        "rounding error makes an equality check fail",
    ],
    "body": "Compare with a tolerance, or move the arithmetic to a fixed-point type.\n",
    "sources": ["https://docs.python.org/3/tutorial/floatingpoint.html"],
    "published_by": "kintsugi-agent",
}


@pytest.fixture(autouse=True)
def _ignore_ambient_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a developer's own Registry and sandbox repo out of the tests."""
    for variable in (SKILLS_DIR_ENV_VAR, SANDBOX_REPO_ENV_VAR):
        monkeypatch.delenv(variable, raising=False)
    assert SKILLS_DIR_ENV_VAR not in os.environ


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    path = tmp_path / "skills"
    path.mkdir()
    return path


@pytest.fixture
def registry(skills_dir: Path) -> SkillRegistry:
    return SkillRegistry(skills_dir=skills_dir)


@pytest.fixture
def populated_registry(registry: SkillRegistry) -> SkillRegistry:
    """A Registry holding two Skills of deliberately unrelated Root Cause Classes."""
    registry.publish_skill(**MUTABLE_DEFAULT_SKILL)
    registry.publish_skill(**FLOAT_EQUALITY_SKILL)
    return registry
