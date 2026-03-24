"""
Shell command execution tool.
Executes shell commands with sandboxing and output capture.
Supports optional sudo mode with a hard deny-list for catastrophic commands.
"""

import asyncio
import re
import subprocess
from typing import Any, Dict, List, Optional

from .base import BaseTool


# Hard deny-list: these commands are NEVER allowed, even with sudo/admin.
CATASTROPHIC_PATTERNS = [
    r'\bmkfs\b',
    r'\bdd\s+if=',
    r'\bshutdown\b',
    r'\breboot\b',
    r'\bpasswd\b',
    r'\buserdel\b',
    r'rm\s+(-\w*\s+)*-rf\s+/',
    r'\bformat\s+[cC]:',
    r'\binit\s+0\b',
    r'\bhalt\b',
]


class ShellTool(BaseTool):
    """
    Execute shell commands on the local system.
    Includes timeout handling, dangerous command filtering, and optional sudo.
    """
    
    name = "shell"
    description = "Execute shell commands"
    actions = ["run", "execute"]
    capabilities_required = ["shell_execute"]
    
    def __init__(self, sandbox=None, config: Optional[dict] = None):
        super().__init__(sandbox, config)
        self.default_timeout = self.config.get('default_timeout', 60)
        self.max_output_length = self.config.get('max_output_length', 4000)
        self.sudo_enabled = self.config.get('sudo_enabled', False)
    
    def _is_catastrophic(self, command: str) -> bool:
        """Check if command matches the hard deny-list."""
        for pattern in CATASTROPHIC_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    async def execute(self, action: str, args: Dict[str, Any]) -> str:
        """Execute a shell command."""
        command = args.get('command', '').strip()
        cwd = args.get('cwd', None)
        timeout = args.get('timeout', self.default_timeout)
        use_sudo = args.get('use_sudo', False)
        
        if not command:
            return "❌ No command provided"

        # Hard deny-list check (runs before sandbox, before sudo)
        if self._is_catastrophic(command):
            self.logger.warning(f"BLOCKED catastrophic command: {command}")
            return "❌ **Blocked:** This command is on the catastrophic deny-list and cannot be executed."
        
        # Validate command through sandbox
        if self.sandbox:
            is_valid, error = self.sandbox.validate_command(command)
            if not is_valid:
                return f"❌ {error}"

        # Apply sudo prefix if requested and enabled
        if use_sudo and self.sudo_enabled and not command.strip().startswith('sudo'):
            command = f"sudo {command}"
        
        self.logger.info(f"Executing shell command: {command}")
        
        try:
            # Run command asynchronously
            result = await self._run_command(command, cwd, timeout)
            return result
        except asyncio.TimeoutError:
            return f"❌ Command timed out after {timeout}s"
        except Exception as e:
            self.logger.error(f"Shell command error: {e}")
            return f"❌ Error: {str(e)}"
    
    async def _run_command(
        self, 
        command: str, 
        cwd: Optional[str], 
        timeout: int
    ) -> str:
        """Run a command and capture output."""
        
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            shell=True
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            raise
        
        # Decode output
        stdout_text = stdout.decode('utf-8', errors='replace').strip()
        stderr_text = stderr.decode('utf-8', errors='replace').strip()
        
        # Format result
        result_parts = []
        
        if stdout_text:
            if len(stdout_text) > self.max_output_length:
                stdout_text = stdout_text[:self.max_output_length] + "\n... (output truncated)"
            result_parts.append(f"📤 **Output:**\n```\n{stdout_text}\n```")
        
        if stderr_text:
            if len(stderr_text) > self.max_output_length:
                stderr_text = stderr_text[:self.max_output_length] + "\n... (output truncated)"
            result_parts.append(f"⚠️ **Stderr:**\n```\n{stderr_text}\n```")
        
        if process.returncode != 0:
            result_parts.append(f"❌ Exit code: {process.returncode}")
        else:
            result_parts.append("✅ Command completed successfully")
        
        if not result_parts:
            result_parts.append("✅ Command completed (no output)")
        
        return "\n\n".join(result_parts)
