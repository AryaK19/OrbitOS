"""
File operations tool.
Read, write, list, and manage files with sandboxing.
"""

import os
import aiofiles
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from .base import BaseTool


class FilesTool(BaseTool):
    """
    Perform file operations on the local filesystem.
    All operations are sandboxed to allowed paths.
    """
    
    name = "files"
    description = "File operations (read, write, list, delete)"
    actions = ["list", "read", "write", "delete", "info"]
    capabilities_required = ["file_read"]  # Base capability, others checked per action
    
    def __init__(self, sandbox=None, config: Optional[dict] = None):
        super().__init__(sandbox, config)
        self.max_file_size = self.config.get('max_file_size_mb', 10) * 1024 * 1024
        self.allowed_extensions = self.config.get('allowed_extensions', [])
    
    async def execute(self, action: str, args: Dict[str, Any]) -> str:
        """Execute a file operation."""
        path = args.get('path', '.').strip()
        
        # Expand path
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        
        # Route to action handler
        handlers = {
            'list': self._list_directory,
            'read': self._read_file,
            'write': self._write_file,
            'delete': self._delete_file,
            'info': self._file_info,
        }
        
        handler = handlers.get(action)
        if not handler:
            return f"❌ Unknown action: {action}"
        
        return await handler(path, args)
    
    async def _list_directory(self, path: str, args: Dict) -> str:
        """List directory contents."""
        # Validate path
        if self.sandbox:
            is_valid, error = self.sandbox.validate_path(path, require_exists=True)
            if not is_valid:
                return f"❌ {error}"
        
        try:
            path_obj = Path(path)
            
            if not path_obj.is_dir():
                return f"❌ Not a directory: {path}"
            
            items = []
            for item in sorted(path_obj.iterdir()):
                try:
                    if item.is_dir():
                        items.append(f"📁 {item.name}/")
                    else:
                        size = item.stat().st_size
                        size_str = self._format_size(size)
                        items.append(f"📄 {item.name} ({size_str})")
                except (PermissionError, OSError):
                    items.append(f"🔒 {item.name} (access denied)")
            
            if not items:
                return f"📂 Directory is empty: `{path}`"
            
            header = f"📂 **Contents of `{path}`:**\n"
            return header + "\n".join(items)
            
        except PermissionError:
            return f"❌ Permission denied: {path}"
        except Exception as e:
            return f"❌ Error listing directory: {str(e)}"
    
    async def _read_file(self, path: str, args: Dict) -> str:
        """Read file contents."""
        if self.sandbox:
            is_valid, error = self.sandbox.validate_path(path, require_exists=True)
            if not is_valid:
                return f"❌ {error}"
        
        try:
            path_obj = Path(path)
            
            if not path_obj.is_file():
                return f"❌ Not a file: {path}"
            
            # Check file size
            size = path_obj.stat().st_size
            if size > self.max_file_size:
                return f"❌ File too large ({self._format_size(size)}). Max: {self._format_size(self.max_file_size)}"
            
            # Read file
            async with aiofiles.open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = await f.read()
            
            # Truncate if needed
            if len(content) > 4000:
                content = content[:4000] + "\n... (content truncated)"
            
            return f"📄 **File: `{path_obj.name}`**\n```\n{content}\n```"
            
        except PermissionError:
            return f"❌ Permission denied: {path}"
        except Exception as e:
            return f"❌ Error reading file: {str(e)}"
    
    async def _write_file(self, path: str, args: Dict) -> str:
        """Write content to a file."""
        content = args.get('content', '')
        
        if not content:
            return "❌ No content provided to write"
        
        if self.sandbox:
            is_valid, error = self.sandbox.validate_path(path)
            if not is_valid:
                return f"❌ {error}"
        
        try:
            path_obj = Path(path)
            
            # Create parent directories if needed
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            size = path_obj.stat().st_size
            return f"✅ Written {self._format_size(size)} to `{path}`"
            
        except PermissionError:
            return f"❌ Permission denied: {path}"
        except Exception as e:
            return f"❌ Error writing file: {str(e)}"
    
    async def _delete_file(self, path: str, args: Dict) -> str:
        """Delete a file (requires file_delete capability)."""
        if self.sandbox:
            is_valid, error = self.sandbox.validate_path(path, require_exists=True)
            if not is_valid:
                return f"❌ {error}"
        
        try:
            path_obj = Path(path)
            
            if path_obj.is_dir():
                return "❌ Cannot delete directories. Use shell command for that."
            
            if not path_obj.exists():
                return f"❌ File not found: {path}"
            
            path_obj.unlink()
            return f"✅ Deleted: `{path}`"
            
        except PermissionError:
            return f"❌ Permission denied: {path}"
        except Exception as e:
            return f"❌ Error deleting file: {str(e)}"
    
    async def _file_info(self, path: str, args: Dict) -> str:
        """Get detailed file/directory information."""
        if self.sandbox:
            is_valid, error = self.sandbox.validate_path(path, require_exists=True)
            if not is_valid:
                return f"❌ {error}"
        
        try:
            path_obj = Path(path)
            stat = path_obj.stat()
            
            info_lines = [
                f"📋 **File Info: `{path_obj.name}`**",
                f"• Type: {'Directory' if path_obj.is_dir() else 'File'}",
                f"• Size: {self._format_size(stat.st_size)}",
                f"• Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}",
                f"• Created: {datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}",
                f"• Path: `{path_obj.absolute()}`",
            ]
            
            return "\n".join(info_lines)
            
        except Exception as e:
            return f"❌ Error getting file info: {str(e)}"
    
    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
