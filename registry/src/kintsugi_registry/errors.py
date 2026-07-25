"""Errors the Registry raises across its tool boundary."""


class RegistryError(Exception):
    """Base class for every error a Registry caller can see."""


class SkillNotFound(RegistryError):
    """No Skill is stored under the requested id."""


class HypothesisRejected(RegistryError):
    """The query was not a Root Cause Hypothesis.

    Raised — rather than returned as a `research` decision — because ADR-0003
    makes "diagnose before you look up" a mechanism, not advice. A caller that
    received `research` here would simply proceed to research, and the guard
    would have enforced nothing.
    """


class MalformedSkill(RegistryError):
    """A stored SKILL.md could not be read as a Skill."""
