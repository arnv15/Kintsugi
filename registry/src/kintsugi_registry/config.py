"""Where the Registry keeps its Skills.

The default is a user-level directory rather than one inside a repo, because
ADR-0001 treats the Registry as a shared store reachable by any agent on any
repo — a location that moves with the working directory would not be one.
"""

from __future__ import annotations

import os
from pathlib import Path

SKILLS_DIR_ENV_VAR = "KINTSUGI_SKILLS_DIR"
DEFAULT_SKILLS_DIR = Path.home() / ".kintsugi" / "skills"

SANDBOX_REPO_ENV_VAR = "KINTSUGI_SANDBOX_REPO"
SKILLS_REMOTE_ENV_VAR = "KINTSUGI_SKILLS_REMOTE"


def resolve_skills_dir(explicit: str | Path | None = None) -> Path:
    """Pick the Skill directory: explicit argument, then environment, then default."""
    if explicit is not None:
        return Path(explicit).expanduser()

    from_env = os.environ.get(SKILLS_DIR_ENV_VAR)
    if from_env:
        return Path(from_env).expanduser()

    return DEFAULT_SKILLS_DIR


def resolve_skills_remote() -> str | None:
    """The shared Skills repo to clone from, if one is configured."""
    return os.environ.get(SKILLS_REMOTE_ENV_VAR) or None


def resolve_sandbox_repo(explicit: str | Path | None = None) -> Path | None:
    """Pick the repo to check a Skill against, or None if there is none.

    ADR-0002 claims Skills are *prevented* from carrying code out of the repo
    they were learned in, so the deployment can configure the repo once and have
    the guard run on every publish — rather than leaving it to a per-call
    argument the agent being constrained could simply omit.
    """
    if explicit is not None:
        return Path(explicit).expanduser()

    from_env = os.environ.get(SANDBOX_REPO_ENV_VAR)
    if from_env:
        return Path(from_env).expanduser()

    return None
