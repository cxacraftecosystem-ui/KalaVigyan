from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError

from app.core.errors import InvalidInput, Refused

from .mcp_ask_tools import ASK_TOOLS
from .mcp_fact_tools import FACT_TOOLS
from .mcp_layout_tools import LAYOUT_TOOLS
from .mcp_page_tools import PAGE_TOOLS
from .mcp_picture_tools import PICTURE_TOOLS
from .mcp_prompts import prompt_list, prompt_result
from .mcp_protocol import (
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    RequestError,
    error_reply,
    initialize_result,
    request_parts,
    result_reply,
    tool_error,
    tool_result,
)
from .mcp_read_tools import READ_TOOLS
from .mcp_resources import resource_list, resource_read, resource_templates
from .mcp_source_tools import SOURCE_TOOLS
from .mcp_steward_tools import STEWARD_TOOLS
from .mcp_structure_tools import STRUCTURE_TOOLS
from .mcp_task_tools import TASK_TOOLS
from .mcp_tool_base import Tool, ToolContext, scope_refusal
from .mcp_work_tools import WORK_TOOLS

__all__ = ["TOOLS", "ToolContext", "answer", "tool_list"]

TOOLS: Mapping[str, Tool] = MappingProxyType(
    {
        tool.name: tool
        for tool in (
            *READ_TOOLS,
            *FACT_TOOLS,
            *WORK_TOOLS,
            *TASK_TOOLS,
            *STEWARD_TOOLS,
            *ASK_TOOLS,
            *PICTURE_TOOLS,
            *LAYOUT_TOOLS,
            *STRUCTURE_TOOLS,
            *SOURCE_TOOLS,
            *PAGE_TOOLS,
        )
    }
)


def tool_list() -> list[dict[str, Any]]:
    return [tool.listed() for tool in TOOLS.values()]


async def answer(message: Any, context: ToolContext) -> dict[str, Any] | None:
    try:
        request_id, method, params, notification = request_parts(message)
    except RequestError as refused:
        return error_reply(refused.request_id, refused.code, refused.message)
    if notification:
        return None
    try:
        return result_reply(request_id, await _dispatch(method, params, context))
    except RequestError as refused:
        return error_reply(request_id, refused.code, refused.message)


async def _dispatch(method: str, params: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    if method == "initialize":
        return initialize_result(params)
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": tool_list()}
    if method == "tools/call":
        return await _call(params, context)
    return _catalogue(method, params, context)


def _catalogue(method: str, params: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    if method == "prompts/list":
        return prompt_list()
    if method == "prompts/get":
        return prompt_result(params)
    if method == "resources/list":
        return resource_list(context.site)
    if method == "resources/templates/list":
        return resource_templates()
    if method == "resources/read":
        return resource_read(params)
    raise RequestError(METHOD_NOT_FOUND, f"the server offers no method {method}")


async def _call(params: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    tool = TOOLS.get(str(params.get("name")))
    if tool is None:
        raise RequestError(INVALID_PARAMS, f"no tool is named {params.get('name')}; tools/list gives them")
    try:
        arguments = tool.arguments.model_validate(params.get("arguments") or {})
    except ValidationError as refused:
        return tool_error(_problems(refused))
    refusal = scope_refusal(tool, context)
    if refusal is not None:
        return tool_error(refusal)
    try:
        reply = await tool.run(context, arguments)
    except (InvalidInput, Refused) as refused:
        if _writes(tool):
            await context.session.rollback()
        return tool_error(str(refused))
    if _writes(tool):
        await context.session.commit()
    return tool_result(reply.model_dump(mode="json", by_alias=True))


def _writes(tool: Tool) -> bool:
    return not tool.annotations.get("readOnlyHint", True)


def _problems(refused: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in problem['loc']) or 'arguments'}: {problem['msg']}"
        for problem in refused.errors()
    )
