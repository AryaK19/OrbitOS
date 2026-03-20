"""
Application launcher tool.
Launch applications on the local system.
"""

import asyncio
import subprocess
import os
from typing import Any, Dict, Optional

from .base import BaseTool
from ..utils.platform import IS_WINDOWS, IS_MAC


class AppsTool(BaseTool):
    """
    Launch applications on the local system.
    Supports common application shortcuts.
    """

    name = "apps"
    description = "Launch applications"
    actions = ["launch", "open", "list"]
    capabilities_required = ["app_launch"]

    WINDOWS_SHORTCUTS = {
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

    MAC_SHORTCUTS = {
        'textedit': 'open -a "TextEdit"',
        'notepad': 'open -a "TextEdit"',
        'calc': 'open -a "Calculator"',
        'calculator': 'open -a "Calculator"',
        'finder': 'open .',
        'explorer': 'open .',
        'files': 'open .',
        'terminal': 'open -a "Terminal"',
        'chrome': 'open -a "Google Chrome"',
        'browser': 'open -a "Safari"',
        'safari': 'open -a "Safari"',
        'firefox': 'open -a "Firefox"',
        'vscode': 'code',
        'code': 'code',
        'settings': 'open "x-apple.systempreferences:"',
        'activity': 'open -a "Activity Monitor"',
        'taskmanager': 'open -a "Activity Monitor"',
        'preview': 'open -a "Preview"',
    }

    LINUX_SHORTCUTS = {
        'notepad': 'gedit',
        'textedit': 'gedit',
        'calc': 'gnome-calculator',
        'calculator': 'gnome-calculator',
        'explorer': 'nautilus .',
        'files': 'nautilus .',
        'terminal': 'gnome-terminal',
        'chrome': 'google-chrome',
        'browser': 'xdg-open http://',
        'firefox': 'firefox',
        'vscode': 'code',
        'code': 'code',
        'settings': 'gnome-control-center',
        'taskmanager': 'gnome-system-monitor',
    }

    @staticmethod
    def _get_default_shortcuts() -> dict:
        if IS_WINDOWS:
            return AppsTool.WINDOWS_SHORTCUTS
        elif IS_MAC:
            return AppsTool.MAC_SHORTCUTS
        else:
            return AppsTool.LINUX_SHORTCUTS
    
    def __init__(self, sandbox=None, config: Optional[dict] = None):
        super().__init__(sandbox, config)
        # Merge platform-specific defaults with config shortcuts
        self.shortcuts = self._get_default_shortcuts().copy()
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
