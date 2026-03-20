"""System information tool wrappers for LangGraph."""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ...tools.system import SystemTool
from .adapter import wrap_tool_action


class EmptyInput(BaseModel):
    """No parameters needed."""
    pass


class ListProcessesInput(BaseModel):
    limit: int = Field(default=20, description="Number of top processes to return")


def create_system_tools(tool: SystemTool) -> list[StructuredTool]:
    return [
        wrap_tool_action(
            tool_instance=tool,
            action="info",
            name="system_info",
            description="Get system info: platform, CPU, memory, disk, uptime.",
            args_schema=EmptyInput,
        ),
        wrap_tool_action(
            tool_instance=tool,
            action="processes",
            name="list_processes",
            description="List running processes sorted by CPU usage.",
            args_schema=ListProcessesInput,
        ),
        wrap_tool_action(
            tool_instance=tool,
            action="disk",
            name="disk_usage",
            description="Get disk usage for all mounted partitions.",
            args_schema=EmptyInput,
        ),
        wrap_tool_action(
            tool_instance=tool,
            action="memory",
            name="memory_usage",
            description="Get detailed memory (RAM) and swap usage.",
            args_schema=EmptyInput,
        ),
        wrap_tool_action(
            tool_instance=tool,
            action="network",
            name="network_info",
            description="Get network interfaces and I/O statistics.",
            args_schema=EmptyInput,
        ),
    ]
