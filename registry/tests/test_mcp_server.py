"""The Registry as an agent actually reaches it — over MCP.

ADR-0001 makes MCP the product surface rather than an integration bolted onto a
library, so the adapter gets exercised through a real client session instead of
being taken on trust.
"""

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from kintsugi_registry.registry import SkillRegistry
from kintsugi_registry.server import build_server

from .conftest import MUTABLE_DEFAULT_SKILL

MATCHING_HYPOTHESIS = (
    "a mutable list is used as a default parameter value so it persists across calls"
)
TRACEBACK_QUERY = (
    'Traceback (most recent call last):\n  File "app/checkout.py", line 42\nValueError: boom'
)


@pytest.fixture
def server(registry: SkillRegistry) -> FastMCP:
    return build_server(registry)


async def test_the_server_exposes_the_four_registry_tools_and_nothing_else(
    server: FastMCP,
) -> None:
    """`clear` is absent on purpose — resetting the shared Registry is an
    operator action (see `cli.py`), not something a Run should be able to do."""
    async with create_connected_server_and_client_session(server) as client:
        listed = await client.list_tools()

    assert sorted(tool.name for tool in listed.tools) == [
        "get_skill",
        "list_skills",
        "publish_skill",
        "search_skills",
    ]


async def test_a_skill_published_over_mcp_is_found_by_a_later_search_over_mcp(
    server: FastMCP,
) -> None:
    async with create_connected_server_and_client_session(server) as client:
        published = await client.call_tool("publish_skill", dict(MUTABLE_DEFAULT_SKILL))
        assert published.structuredContent is not None
        assert published.structuredContent["published"] is True

        found = await client.call_tool("search_skills", {"hypothesis": MATCHING_HYPOTHESIS})
        assert found.structuredContent is not None
        assert found.structuredContent["decision"] == "reuse"
        assert found.structuredContent["matches"][0]["id"] == "mutable-default-argument"

        fetched = await client.call_tool("get_skill", {"skill_id": "mutable-default-argument"})
        assert fetched.structuredContent is not None
        assert fetched.structuredContent["name"] == "Mutable default argument"


async def test_a_traceback_query_comes_back_as_an_error_the_caller_can_act_on(
    server: FastMCP,
) -> None:
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("search_skills", {"hypothesis": TRACEBACK_QUERY})

    assert result.isError is True
    message = "\n".join(block.text for block in result.content if block.type == "text")
    assert "traceback" in message.lower()
    assert "hypothesis" in message.lower()


async def test_asking_for_a_skill_that_is_not_there_comes_back_as_an_error(
    server: FastMCP,
) -> None:
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("get_skill", {"skill_id": "no-such-skill"})

    assert result.isError is True
