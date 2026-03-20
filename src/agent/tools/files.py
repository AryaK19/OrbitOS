"""File operations tool wrappers for LangGraph."""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ...tools.files import FilesTool
from .adapter import wrap_tool_action


class ListDirectoryInput(BaseModel):
    path: str = Field(default=".", description="Directory path to list")


class ReadFileInput(BaseModel):
    path: str = Field(description="Absolute or relative file path to read")


class WriteFileInput(BaseModel):
    path: str = Field(description="File path to write to")
    content: str = Field(description="Content to write to the file")


class DeleteFileInput(BaseModel):
    path: str = Field(description="File path to delete")


class FileInfoInput(BaseModel):
    path: str = Field(description="File or directory path to get info about")


def create_files_tools(tool: FilesTool) -> list[StructuredTool]:
    return [
        wrap_tool_action(
            tool_instance=tool,
            action="list",
            name="list_directory",
            description="List the contents of a directory (files and subdirectories).",
            args_schema=ListDirectoryInput,
        ),
        wrap_tool_action(
            tool_instance=tool,
            action="read",
            name="read_file",
            description="Read the contents of a file. Max 4000 chars returned.",
            args_schema=ReadFileInput,
        ),
        wrap_tool_action(
            tool_instance=tool,
            action="write",
            name="write_file",
            description="Write content to a file. Creates parent directories if needed.",
            args_schema=WriteFileInput,
        ),
        wrap_tool_action(
            tool_instance=tool,
            action="delete",
            name="delete_file",
            description="Delete a file (not directories).",
            args_schema=DeleteFileInput,
        ),
        wrap_tool_action(
            tool_instance=tool,
            action="info",
            name="file_info",
            description="Get detailed info about a file or directory (size, dates, type).",
            args_schema=FileInfoInput,
        ),
    ]
