"""Application launcher tool wrapper for LangGraph."""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ...tools.apps import AppsTool
from .adapter import wrap_tool_action


class LaunchApplicationInput(BaseModel):
    app: str = Field(
        description=(
            "Application name or shortcut to launch "
            "(e.g. 'chrome', 'vscode', 'terminal', 'calculator')"
        )
    )


def create_apps_tools(tool: AppsTool) -> list[StructuredTool]:
    return [
        wrap_tool_action(
            tool_instance=tool,
            action="launch",
            name="launch_application",
            description=(
                "Launch a desktop application by name or shortcut. "
                "Common shortcuts: chrome, vscode, terminal, calculator, finder."
            ),
            args_schema=LaunchApplicationInput,
        ),
    ]
