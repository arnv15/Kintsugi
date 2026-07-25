"""Keeping the Skill directory in step with a shared git repository.

ADR-0001 treats the Registry as reachable by any agent on any machine, which a
directory on one laptop is not. When the Skill directory is itself a git
worktree root, each published Skill is committed and pushed, and the git history
becomes the Registry's provenance record — who published which Skill, and when.

Refreshing is deliberately *not* done per search. ADR-0006 makes wall-clock a
reported metric, and a network round trip inside `search_skills` would land in
the middle of the number being measured. The Registry pulls when it starts and
when it is explicitly asked to.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

COMMIT_EMAIL = "registry@kintsugi.local"
FALLBACK_COMMITTER = "Kintsugi Skill Registry"
GIT_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class SyncOutcome:
    """What happened when the Registry tried to reach the shared repo."""

    pushed: bool
    detail: str = ""


class NoRemote:
    """The Skill directory is a plain folder, so there is nothing to sync.

    A null object rather than a `None` the Registry has to keep checking: the
    difference between a shared Registry and a local one belongs here, not in
    branches scattered through `publish_skill`.
    """

    def refresh(self) -> SyncOutcome:
        return SyncOutcome(pushed=False, detail="Skill directory is not a git repository.")

    def record(self, skill_id: str, published_by: str) -> SyncOutcome:
        return SyncOutcome(pushed=False, detail="Skill directory is not a git repository.")


class GitRemote:
    """A Skill directory that is a git worktree root with somewhere to push to."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def refresh(self) -> SyncOutcome:
        """Bring local Skills up to date with the shared repo.

        A failure is reported, never raised: an agent that cannot reach GitHub
        should still be able to search the Skills it already has.
        """
        pulled = self._git("pull", "--ff-only")
        if pulled.returncode != 0:
            return SyncOutcome(pushed=False, detail=_explain("pull", pulled))
        return SyncOutcome(pushed=False, detail="Refreshed from the shared repo.")

    def record(self, skill_id: str, published_by: str) -> SyncOutcome:
        """Commit the Skill and push it, reporting rather than raising on failure.

        The Skill is already on disk by the time this runs, so every path out of
        here leaves it published locally. Losing a push is recoverable; losing
        the Skill an agent just earned is not.
        """
        staged = self._git("add", "--", skill_id)
        if staged.returncode != 0:
            return SyncOutcome(pushed=False, detail=_explain("add", staged))

        committed = self._commit(skill_id, published_by)
        if committed.returncode != 0:
            return SyncOutcome(pushed=False, detail=_explain("commit", committed))

        pushed = self._git("push")
        if pushed.returncode != 0:
            # Most likely another agent published first. Replay on top and retry
            # once; anything still failing is reported for a person to look at.
            rebased = self._git("pull", "--rebase")
            if rebased.returncode != 0:
                return SyncOutcome(pushed=False, detail=_explain("pull --rebase", rebased))
            pushed = self._git("push")
            if pushed.returncode != 0:
                return SyncOutcome(pushed=False, detail=_explain("push", pushed))

        return SyncOutcome(pushed=True, detail=f"Pushed {self._head()} to the shared repo.")

    def _commit(self, skill_id: str, published_by: str) -> subprocess.CompletedProcess[str]:
        """Commit with the publishing agent as author, so provenance lives in git.

        `user.name`/`user.email` are supplied for this one command so a machine
        with no git identity configured can still publish.
        """
        return self._git(
            "-c",
            f"user.name={FALLBACK_COMMITTER}",
            "-c",
            f"user.email={COMMIT_EMAIL}",
            "commit",
            "--author",
            f"{published_by} <{COMMIT_EMAIL}>",
            "--message",
            f"Publish Skill: {skill_id} ({published_by})",
        )

    def _head(self) -> str:
        result = self._git("rev-parse", "--short", "HEAD")
        return result.stdout.strip() if result.returncode == 0 else "the commit"

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )


def _explain(step: str, result: subprocess.CompletedProcess[str]) -> str:
    reason = (result.stderr or result.stdout).strip().splitlines()
    return f"git {step} failed: {reason[-1] if reason else 'no output'}"


def ensure_clone(root: Path, remote: str | None) -> str:
    """Clone the shared Skills repo into `root` if it isn't there yet.

    This is what makes third-party setup a single environment variable: point
    `KINTSUGI_SKILLS_REMOTE` at the shared repo and the first run fetches every
    Skill published so far.
    """
    if remote is None:
        return "No shared Skills repo configured."
    if (root / ".git").is_dir():
        return f"Using the existing clone at {root}."
    if root.is_dir() and any(root.iterdir()):
        return f"{root} already holds files and is not a clone; leaving it alone."

    root.parent.mkdir(parents=True, exist_ok=True)
    cloned = subprocess.run(
        ["git", "clone", remote, str(root)],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS * 4,
    )
    if cloned.returncode != 0:
        return _explain("clone", cloned)
    return f"Cloned {remote} into {root}."


def build_sync(root: Path) -> NoRemote | GitRemote:
    """Pick a sync strategy by looking at the Skill directory.

    The Skill directory must itself be a git worktree root with a remote. Merely
    being nested in another repository is not enough: a rehearsal store must
    never commit or push through its parent checkout.
    """
    if not root.is_dir():
        return NoRemote()

    top_level = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    if top_level.returncode != 0:
        return NoRemote()
    if Path(top_level.stdout.strip()).resolve() != root.resolve():
        return NoRemote()

    remotes = subprocess.run(
        ["git", "remote"], cwd=root, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS
    )
    if remotes.returncode != 0 or not remotes.stdout.strip():
        return NoRemote()

    return GitRemote(root)
