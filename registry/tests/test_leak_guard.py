"""A Skill may not carry code out of the repo it was learned in.

ADR-0002 permits an illustrative snippet because a worked example teaches a
Root Cause Class far better than a paragraph — and then closes the hole that
opens, by refusing at publish time any snippet that is just the real diff.
"""

from pathlib import Path

import pytest

from kintsugi_registry.config import SANDBOX_REPO_ENV_VAR
from kintsugi_registry.errors import RegistryError
from kintsugi_registry.registry import SkillRegistry

from .conftest import MUTABLE_DEFAULT_SKILL

REPO_SOURCE = """\
from decimal import Decimal


def add_item(sku, basket=[]):
    basket.append(sku)
    return basket


def total(basket):
    return sum(Decimal(item.price) for item in basket)
"""

LEAKED_ILLUSTRATION = """\
The default is evaluated once, so every call shares one basket:

```python
def add_item(sku, basket=[]):
    basket.append(sku)
    return basket
```
"""

# Same code, reflowed and re-indented — a rename-free "disguise" that survives
# only until the comparison is whitespace-normalized.
REFLOWED_ILLUSTRATION = """\
The default is evaluated once:

```python
def add_item(sku,   basket=[]):

        basket.append(sku)
        return basket
```
"""

SYNTHETIC_ILLUSTRATION = """\
Written from scratch in a domain the bug never touched:

```python
def remember(word, seen=[]):
    seen.append(word)
    return seen
```

Bind the default to a sentinel instead, and build the list inside the body.
"""

# Two lines, so under the floor at which a shared fragment means anything.
SHORT_ILLUSTRATION = """\
The fix is to stop returning the shared object:

```python
    basket.append(sku)
    return basket
```
"""


@pytest.fixture
def sandbox_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sandbox"
    (repo / "shop").mkdir(parents=True)
    (repo / "shop" / "cart.py").write_text(REPO_SOURCE, encoding="utf-8")
    return repo


def _publish(registry: SkillRegistry, body: str, repo: Path) -> dict:
    return registry.publish_skill(
        **{**MUTABLE_DEFAULT_SKILL, "body": body}, repo_path=str(repo)
    )


def test_publish_is_refused_when_a_snippet_appears_verbatim_in_the_repo(
    registry: SkillRegistry, sandbox_repo: Path
) -> None:
    result = _publish(registry, LEAKED_ILLUSTRATION, sandbox_repo)

    assert result["published"] is False
    assert registry.list_skills()["count"] == 0


def test_the_refusal_names_the_offending_snippet_and_says_how_to_fix_it(
    registry: SkillRegistry, sandbox_repo: Path
) -> None:
    result = _publish(registry, LEAKED_ILLUSTRATION, sandbox_repo)

    feedback = result["feedback"]
    assert "shop/cart.py" in feedback, "the caller is told where the collision is"
    assert "def add_item" in result["leaked_snippets"][0]["snippet"]
    assert "synthetic" in feedback.lower(), "the caller is told what to do instead"


def test_reindenting_a_leaked_snippet_does_not_get_it_past_the_guard(
    registry: SkillRegistry, sandbox_repo: Path
) -> None:
    result = _publish(registry, REFLOWED_ILLUSTRATION, sandbox_repo)

    assert result["published"] is False


def test_a_synthetic_illustration_publishes(
    registry: SkillRegistry, sandbox_repo: Path
) -> None:
    result = _publish(registry, SYNTHETIC_ILLUSTRATION, sandbox_repo)

    assert result["published"] is True
    assert result["leak_check"] == "passed"
    assert registry.get_skill(result["skill_id"])["body"] == SYNTHETIC_ILLUSTRATION


def test_a_snippet_of_two_lines_or_fewer_is_below_the_guards_floor(
    registry: SkillRegistry, sandbox_repo: Path
) -> None:
    result = _publish(registry, SHORT_ILLUSTRATION, sandbox_repo)

    assert result["published"] is True


def test_publishing_with_no_repo_anywhere_records_that_the_guard_did_not_run(
    registry: SkillRegistry,
) -> None:
    result = registry.publish_skill(**{**MUTABLE_DEFAULT_SKILL, "body": LEAKED_ILLUSTRATION})

    assert result["published"] is True
    assert result["leak_check"] == "skipped"


def test_a_configured_sandbox_repo_guards_publishes_that_do_not_supply_one(
    registry: SkillRegistry, sandbox_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-0002 says Skills are *prevented* from carrying code out of the repo,
    so the guard cannot depend on the agent it constrains passing `repo_path`."""
    monkeypatch.setenv(SANDBOX_REPO_ENV_VAR, str(sandbox_repo))

    result = registry.publish_skill(**{**MUTABLE_DEFAULT_SKILL, "body": LEAKED_ILLUSTRATION})

    assert result["published"] is False


def test_a_repo_path_that_does_not_exist_is_an_error_not_a_quiet_pass(
    registry: SkillRegistry, tmp_path: Path
) -> None:
    with pytest.raises(RegistryError):
        _publish(registry, LEAKED_ILLUSTRATION, tmp_path / "nowhere")
