"""
Application launcher tool.
Launch applications on the local system.
"""

import asyncio
import subprocess
import os
from typing import Any, Dict, Optional

from .base import BaseTool


class AppsTool(BaseTool):
    """
    Launch applications on the local system.
    Supports common application shortcuts.
    """
    
    name = "apps"
    description = "Launch applications"
    actions = ["launch", "open", "list"]
    capabilities_required = ["app_launch"]
    
    # Default application shortcuts for Windows
    DEFAULT_SHORTCUTS = {
        'notepad': 'notepad.exe',
        'calc': 'calc.exe',
        'calculator': 'calc.exe',
        'explorer': 'explorer.exe',
        'files': 'explorer.exe',
        'cmd': 'cmd.exe',
        'terminal': 'wt.exe',
        'powershell': 'powershell.exe',
        'chrome': 'start chrome',
        'browser': 'start chrome',
        'firefox': 'start firefox',
        'edge': 'start msedge',
        'vscode': 'code',
        'code': 'code',
        'word': 'start winword',
        'excel': 'start excel',
        'paint': 'mspaint.exe',
        'snip': 'snippingtool.exe',
        'settings': 'start ms-settings:',
        'task': 'taskmgr.exe',
        'taskmanager': 'taskmgr.exe',
    }
    
    def __init__(self, sandbox=None, config: Optional[dict] = None):
        super().__init__(sandbox, config)
        # Merge default shortcuts with config shortcuts
        self.shortcuts = self.DEFAULT_SHORTCUTS.copy()
        custom_shortcuts = self.config.get('shortcuts', {})
        self.shortcuts.update(custom_shortcuts)
    
    async def execute(self, action: str, args: Dict[str, Any]) -> str:
        """Execute an apps action."""
        if action == 'list':
            return self._list_shortcuts()
        
        app = args.get('app', '').strip().lower()
        
        if not app:
            return "❌ No application specified\n\nUse `/apps list` to see available shortcuts."
        
        return await self._launch_app(app)
    
    async def _launch_app(self, app: str) -> str:
        """Launch an application."""
        # Check if it's a shortcut
        command = self.shortcuts.get(app, app)
        
        self.logger.info(f"Launching application: {app} -> {command}")
        
        try:
            # Use subprocess for launching
            if os.name == 'nt':  # Windows
                # Use start command for better handling
                if not command.startswith('start '):
                    process = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                else:
                    process = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
            else:  # Linux/Mac
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            
            # Wait briefly to check if process started
            await asyncio.sleep(0.5)
            
            if process.poll() is None or process.returncode == 0:
                return f"✅ Launched: **{app}**"
            else:
                return f"⚠️ Application may have exited immediately: {app}"
                
        except FileNotFoundError:
            return f"❌ Application not found: {app}\n\nTry using the full path or check if it's installed."
        except Exception as e:
            self.logger.error(f"Error launching app: {e}")
            return f"❌ Failed to launch: {str(e)}"
    
    def _list_shortcuts(self) -> str:
        """List available application shortcuts."""
        lines = ["🚀 **Available Application Shortcuts:**\n"]
        
        # Group shortcuts by category
        categories = {
            'System': ['explorer', 'terminal', 'cmd', 'powershell', 'taskmanager', 'settings'],
            'Browsers': ['chrome', 'firefox', 'edge', 'browser'],
            'Editors': ['notepad', 'vscode', 'code'],
            'Office': ['word', 'excel'],
            'Utilities': ['calc', 'calculator', 'paint', 'snip'],
        }
        
        for category, apps in categories.items():
            available = [app for app in apps if app in self.shortcuts]
            if available:
                lines.append(f"**{category}:**")
                for app in available:
                    lines.append(f"  • `{app}` → {self.shortcuts[app]}")
                lines.append("")
        
        lines.append("💡 You can also use any executable name or path directly.")
        
        return "\n".join(lines)
