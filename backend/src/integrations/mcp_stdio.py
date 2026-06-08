"""Spawn local MCP servers over stdio and call tools (used by Ross integrations)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def tool_result_text(result: Any) -> str:
    parts: list[str] = []
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


@asynccontextmanager
async def mcp_session(command: str, args: list[str]):
    params = StdioServerParameters(command=command, args=args)
    async with stdio_client(params) as (read, write):  # noqa: SIM117
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def call_mcp_tool(
    command: str,
    args: list[str],
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> str:
    logger.debug("MCP tool {} via {} {}", tool_name, command, args)
    async with mcp_session(command, args) as session:
        result = await session.call_tool(tool_name, arguments=arguments or {})
        if result.isError:
            detail = tool_result_text(result) or "unknown MCP tool error"
            raise RuntimeError(detail)
        return tool_result_text(result)
