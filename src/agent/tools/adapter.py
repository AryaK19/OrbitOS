"""
Generic adapter to wrap OrbitOS BaseTool actions as LangChain StructuredTools.
"""

from typing import Type

from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from ...tools.base import BaseTool


def wrap_tool_action(
    tool_instance: BaseTool,
    action: str,
    name: str,
    description: str,
    args_schema: Type[BaseModel],
) -> StructuredTool:
    """Wrap a single BaseTool action as a LangChain StructuredTool.

    Args:
        tool_instance: The OrbitOS BaseTool instance.
        action: The action string to pass to tool.execute().
        name: LangChain tool name (what the LLM sees).
        description: Tool description for the LLM.
        args_schema: Pydantic model defining the tool's input parameters.

    Returns:
        A LangChain StructuredTool that delegates to the BaseTool.
    """

    async def _run(**kwargs) -> str:
        return await tool_instance.execute(action, kwargs)

    return StructuredTool.from_function(
        coroutine=_run,
        name=name,
        description=description,
        args_schema=args_schema,
    )
