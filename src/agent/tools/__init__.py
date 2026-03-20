"""
LangGraph tool wrappers for OrbitOS.
Adapts existing BaseTool instances into LangChain StructuredTools.
"""

from langchain_core.tools import StructuredTool

from ...tools.base import ToolRegistry
from .shell import create_shell_tools
from .files import create_files_tools
from .python import create_python_tools
from .apps import create_apps_tools
from .system import create_system_tools


def create_all_tools(tool_registry: ToolRegistry) -> list[StructuredTool]:
    """Create all LangChain tools from registered OrbitOS tools.

    Args:
        tool_registry: The OrbitOS ToolRegistry containing initialized BaseTool instances.

    Returns:
        List of LangChain StructuredTools ready for use with LangGraph.
    """
    tools: list[StructuredTool] = []

    # Map registry names to their tool creator functions
    creators = {
        "shell": create_shell_tools,
        "files": create_files_tools,
        "python": create_python_tools,
        "apps": create_apps_tools,
        "system": create_system_tools,
    }

    for name, creator in creators.items():
        instance = tool_registry.get(name)
        if instance:
            tools.extend(creator(instance))

    return tools
