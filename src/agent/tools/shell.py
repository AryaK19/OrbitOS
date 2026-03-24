"""Shell tool wrapper for LangGraph."""

from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ...tools.shell import ShellTool
from .adapter import wrap_tool_action


class RunShellCommandInput(BaseModel):
    command: str = Field(description="The shell command to execute")
    cwd: Optional[str] = Field(default=None, description="Working directory (absolute path)")
    timeout: int = Field(default=60, description="Timeout in seconds")
    use_sudo: bool = Field(default=False, description="Run the command with sudo for elevated privileges. Use when you get permission denied errors.")


def create_shell_tools(tool: ShellTool) -> list[StructuredTool]:
    return [
        wrap_tool_action(
            tool_instance=tool,
            action="run",
            name="run_shell_command",
            description=(
                "Execute a shell command on the local system. "
                "Returns stdout, stderr, and exit code. "
                "Set use_sudo=true if you need elevated privileges (e.g., editing system configs, restarting services)."
            ),
            args_schema=RunShellCommandInput,
        ),
    ]
