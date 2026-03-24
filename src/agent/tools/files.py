"""File operations tool wrappers for LangGraph."""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ...tools.files import FilesTool
from .adapter import wrap_tool_action


class ListDirectoryInput(BaseModel):
    path: str = Field(default=".", description="Directory path to list")
    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    filter: str = Field(default="", description="Optional filename glob pattern, e.g. *.py")


class SearchFilesInput(BaseModel):
    path: str = Field(default=".", description="Root directory path to search recursively")
    filter: str = Field(default="*", description="Filename glob pattern, e.g. *.pdf")
    max_results: int = Field(default=50, ge=1, le=200, description="Maximum files to return")
    timeout_seconds: float = Field(default=3.0, ge=0.5, le=30.0, description="Search timeout")


class ReadFileInput(BaseModel):
    path: str = Field(description="Absolute or relative file path to read")


class WriteFileInput(BaseModel):
    path: str = Field(description="File path to write to")
    content: str = Field(description="Content to write to the file")


class DeleteFileInput(BaseModel):
    path: str = Field(description="File path to delete")


class RenamePathInput(BaseModel):
    path: str = Field(description="Source file or directory path")
    new_path: str = Field(description="Destination path with new name")


class MovePathInput(BaseModel):
    path: str = Field(description="Source file or directory path")
    destination: str = Field(description="Destination path")


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
            action="search",
            name="search_files",
            description="Recursively search files by glob pattern with timeout and result cap.",
            args_schema=SearchFilesInput,
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
            action="rename",
            name="rename_path",
            description="Rename a file or directory.",
            args_schema=RenamePathInput,
        ),
        wrap_tool_action(
            tool_instance=tool,
            action="move",
            name="move_path",
            description="Move a file or directory to another location.",
            args_schema=MovePathInput,
        ),
        wrap_tool_action(
            tool_instance=tool,
            action="info",
            name="file_info",
            description="Get detailed info about a file or directory (size, dates, type).",
            args_schema=FileInfoInput,
        ),
    ]
