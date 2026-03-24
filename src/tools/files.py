"""
File operations tool.
Read, write, list, and manage files with sandboxing.
"""

import asyncio
import fnmatch
import json
import os
import aiofiles
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import math
import time

from .base import BaseTool


class FilesTool(BaseTool):
    """
    Perform file operations on the local filesystem.
    All operations are sandboxed to allowed paths.
    """
    
    name = "files"
    description = "File operations (read, write, list, delete)"
    actions = ["list", "search", "read", "write", "delete", "rename", "move", "info"]
    capabilities_required = ["file_read"]  # Base capability, others checked per action
    
    def __init__(self, sandbox=None, config: Optional[dict] = None):
        super().__init__(sandbox, config)
        self.max_file_size = self.config.get('max_file_size_mb', 10) * 1024 * 1024
        self.allowed_extensions = self.config.get('allowed_extensions', [])
        self.max_list_limit = int(self.config.get('max_list_limit', 100))
        self.max_search_results = int(self.config.get('max_search_results', 50))
        configured_ttl = int(self.config.get('list_cache_ttl_seconds', 20))
        self.list_cache_ttl_seconds = max(15, min(30, configured_ttl))
        self.search_timeout_seconds = float(self.config.get('search_timeout_seconds', 3.0))
        self._list_cache: Dict[Tuple[str, int, int, str], Tuple[float, Dict[str, Any]]] = {}
    
    async def execute(self, action: str, args: Dict[str, Any]) -> str:
        """Execute a file operation."""
        path = str(args.get('path', '.')).strip()
        
        # Expand path
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        
        # Route to action handler
        handlers = {
            'list': self._list_directory,
            'search': self._search_files,
            'read': self._read_file,
            'write': self._write_file,
            'delete': self._delete_file,
            'rename': self._rename_path,
            'move': self._move_path,
            'info': self._file_info,
        }
        
        handler = handlers.get(action)
        if not handler:
            return f"❌ Unknown action: {action}"
        
        return await handler(path, args)
    
    async def _list_directory(self, path: str, args: Dict) -> str:
        """List directory contents with pagination/filtering and cache."""
        if self.sandbox:
            is_valid, error = self.sandbox.validate_path(path, require_exists=True)
            if not is_valid:
                return f"❌ {error}"
        
        try:
            page = max(1, int(args.get('page', 1)))
            limit = int(args.get('limit', 20))
            limit = max(1, min(self.max_list_limit, limit))
            pattern = str(args.get('filter', args.get('pattern', '')) or '').strip()

            payload = await self.list_directory(path=path, page=page, limit=limit, pattern=pattern)
            return json.dumps(payload, ensure_ascii=True, indent=2)
            
        except PermissionError:
            return f"❌ Permission denied: {path}"
        except Exception as e:
            return f"❌ Error listing directory: {str(e)}"

    async def list_directory(self, path: str, page: int = 1, limit: int = 20, pattern: str = "") -> Dict[str, Any]:
        """Fast non-recursive directory listing with pagination and filtering."""
        cache_key = (str(Path(path).resolve()), page, limit, pattern)
        now = time.monotonic()

        cached_entry = self._list_cache.get(cache_key)
        if cached_entry:
            cached_at, payload = cached_entry
            if now - cached_at <= self.list_cache_ttl_seconds:
                payload['from_cache'] = True
                return payload
            self._list_cache.pop(cache_key, None)

        payload = await asyncio.to_thread(
            self._list_directory_sync,
            path,
            page,
            limit,
            pattern,
        )

        payload['from_cache'] = False
        self._list_cache[cache_key] = (now, payload.copy())
        return payload

    def _list_directory_sync(self, path: str, page: int, limit: int, pattern: str) -> Dict[str, Any]:
        """CPU/IO bound listing implementation, safe to run in thread."""
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        if not path_obj.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")

        records: List[Dict[str, Any]] = []
        with os.scandir(path_obj) as iterator:
            for entry in iterator:
                if pattern and not fnmatch.fnmatch(entry.name, pattern):
                    continue
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    stat = entry.stat(follow_symlinks=False)
                    records.append({
                        'name': entry.name,
                        'path': str(Path(entry.path).resolve()),
                        'is_dir': is_dir,
                        'size': 0 if is_dir else stat.st_size,
                        'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds'),
                    })
                except (PermissionError, FileNotFoundError, OSError):
                    continue

        # Deterministic order: directories first, then filename (case-insensitive).
        records.sort(key=lambda item: (not item['is_dir'], item['name'].lower(), item['name']))

        total = len(records)
        total_pages = max(1, math.ceil(total / limit)) if total else 0
        start = (page - 1) * limit
        end = start + limit
        paged = records[start:end] if total else []

        return {
            'path': str(path_obj.resolve()),
            'page': page,
            'limit': limit,
            'filter': pattern or None,
            'total_count': total,
            'total_pages': total_pages,
            'has_next_page': page < total_pages,
            'items': paged,
        }

    async def _search_files(self, path: str, args: Dict) -> str:
        """Recursive search with timeout safety and result cap."""
        if self.sandbox:
            is_valid, error = self.sandbox.validate_path(path, require_exists=True)
            if not is_valid:
                return f"❌ {error}"

        try:
            pattern = str(args.get('filter', args.get('pattern', '*')) or '*').strip() or '*'
            max_results = int(args.get('max_results', self.max_search_results))
            max_results = max(1, min(self.max_search_results, max_results))
            timeout_seconds = float(args.get('timeout_seconds', self.search_timeout_seconds))
            timeout_seconds = max(0.5, timeout_seconds)

            payload = await asyncio.to_thread(
                self.search_files,
                path,
                pattern,
                max_results,
                timeout_seconds,
            )
            return json.dumps(payload, ensure_ascii=True, indent=2)
        except PermissionError:
            return f"❌ Permission denied: {path}"
        except Exception as e:
            return f"❌ Error searching files: {str(e)}"

    def search_files(
        self,
        path: str,
        pattern: str = '*',
        max_results: int = 50,
        timeout_seconds: float = 3.0,
    ) -> Dict[str, Any]:
        """Recursive file search constrained by timeout and max result count."""
        root = Path(path)
        if not root.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")

        started = time.monotonic()
        timed_out = False
        results: List[Dict[str, Any]] = []
        pending: List[Path] = [root]

        while pending and len(results) < max_results:
            if time.monotonic() - started > timeout_seconds:
                timed_out = True
                break

            current = pending.pop()
            try:
                with os.scandir(current) as iterator:
                    entries = sorted(iterator, key=lambda entry: entry.name.lower())
            except (PermissionError, FileNotFoundError, OSError):
                continue

            for entry in entries:
                if time.monotonic() - started > timeout_seconds:
                    timed_out = True
                    break

                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    if is_dir:
                        pending.append(Path(entry.path))
                        continue

                    if not fnmatch.fnmatch(entry.name, pattern):
                        continue

                    stat = entry.stat(follow_symlinks=False)
                    results.append({
                        'name': entry.name,
                        'path': str(Path(entry.path).resolve()),
                        'is_dir': False,
                        'size': stat.st_size,
                        'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds'),
                    })

                    if len(results) >= max_results:
                        break
                except (PermissionError, FileNotFoundError, OSError):
                    continue

            if timed_out:
                break

        results.sort(key=lambda item: item['path'].lower())

        return {
            'path': str(root.resolve()),
            'filter': pattern,
            'max_results': max_results,
            'timeout_seconds': timeout_seconds,
            'timed_out': timed_out,
            'returned_count': len(results),
            'items': results,
        }
    
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

            self._invalidate_list_cache()
            
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
            self._invalidate_list_cache()
            return f"✅ Deleted: `{path}`"
            
        except PermissionError:
            return f"❌ Permission denied: {path}"
        except Exception as e:
            return f"❌ Error deleting file: {str(e)}"

    async def _rename_path(self, path: str, args: Dict) -> str:
        """Rename file or directory in-place."""
        new_path = str(args.get('new_path') or args.get('destination') or args.get('content') or '').strip()
        if not new_path:
            return "❌ Missing new path. Provide `new_path` or `destination`."

        new_path = os.path.expanduser(new_path)
        if not os.path.isabs(new_path):
            new_path = os.path.abspath(new_path)

        if self.sandbox:
            is_valid, error = self.sandbox.validate_path(path, require_exists=True)
            if not is_valid:
                return f"❌ {error}"
            is_valid, error = self.sandbox.validate_path(new_path)
            if not is_valid:
                return f"❌ {error}"

        try:
            src = Path(path)
            dst = Path(new_path)
            src.rename(dst)
            self._invalidate_list_cache()
            return f"✅ Renamed: `{src}` -> `{dst}`"
        except PermissionError:
            return f"❌ Permission denied: {path}"
        except Exception as e:
            return f"❌ Error renaming path: {str(e)}"

    async def _move_path(self, path: str, args: Dict) -> str:
        """Move file or directory to another location."""
        destination = str(args.get('destination') or args.get('new_path') or args.get('content') or '').strip()
        if not destination:
            return "❌ Missing destination path. Provide `destination` or `new_path`."

        destination = os.path.expanduser(destination)
        if not os.path.isabs(destination):
            destination = os.path.abspath(destination)

        if self.sandbox:
            is_valid, error = self.sandbox.validate_path(path, require_exists=True)
            if not is_valid:
                return f"❌ {error}"
            is_valid, error = self.sandbox.validate_path(destination)
            if not is_valid:
                return f"❌ {error}"

        try:
            src = Path(path)
            dst = Path(destination)
            src.replace(dst)
            self._invalidate_list_cache()
            return f"✅ Moved: `{src}` -> `{dst}`"
        except PermissionError:
            return f"❌ Permission denied: {path}"
        except Exception as e:
            return f"❌ Error moving path: {str(e)}"
    
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

    def _invalidate_list_cache(self):
        """Invalidate directory listing cache after filesystem mutations."""
        self._list_cache.clear()
