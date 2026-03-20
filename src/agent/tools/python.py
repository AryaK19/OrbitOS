"""Python execution tool wrapper for LangGraph."""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ...tools.python_exec import PythonExecTool
from .adapter import wrap_tool_action


class RunPythonCodeInput(BaseModel):
    code: str = Field(description="Python code to execute")


def create_python_tools(tool: PythonExecTool) -> list[StructuredTool]:
    return [
        wrap_tool_action(
            tool_instance=tool,
            action="execute",
            name="run_python_code",
            description=(
                "Execute Python code and return the result. "
                "Captures stdout, stderr, and return value. 30s timeout."
            ),
            args_schema=RunPythonCodeInput,
        ),
    ]
