"""
Sandbox utility for the Remote MCP Control System.
Provides path and command sandboxing for security.
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Set
from dataclasses import dataclass, field

from .logger import get_logger


@dataclass
class SandboxConfig:
    """Configuration for the sandbox."""
    allowed_paths: List[str]
    blocked_commands: List[str]
    blocked_imports: List[str]
    python_timeout: int = 30
    blocked_paths: List[str] = field(default_factory=list)


class Sandbox:
    """
    Sandbox for validating and restricting operations.
    Ensures file operations stay within allowed paths and
    blocks dangerous commands.
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.logger = get_logger()
        
        if config:
            self.allowed_paths = [Path(p).resolve() for p in config.allowed_paths]
            self.blocked_patterns = [re.compile(p, re.IGNORECASE) for p in config.blocked_commands]
            self.blocked_imports = set(config.blocked_imports)
            self.python_timeout = config.python_timeout
            self.blocked_paths = [Path(p).resolve() for p in config.blocked_paths]
        else:
            # Default safe configuration
            self.allowed_paths = [Path.home().resolve()]
            self.blocked_patterns = [
                # Cross-platform: block only standalone shutdown/restart commands,
                # NOT as arguments to systemctl/service etc.
                re.compile(r'^\s*(?:sudo\s+)?shutdown\b', re.IGNORECASE),
                re.compile(r'^\s*(?:sudo\s+)?restart\b', re.IGNORECASE),
                re.compile(r'^\s*(?:sudo\s+)?reboot\b', re.IGNORECASE),
                re.compile(r'^\s*(?:sudo\s+)?halt\b', re.IGNORECASE),
                re.compile(r'^\s*(?:sudo\s+)?init\s+0\b', re.IGNORECASE),
                # Windows
                re.compile(r'format\s+[a-z]:', re.IGNORECASE),
                re.compile(r'del\s+/s\s+/q\s+[a-z]:', re.IGNORECASE),
                # Unix/macOS
                re.compile(r'rm\s+(-\w*\s+)*-rf\s+/', re.IGNORECASE),
                re.compile(r'mkfs\b', re.IGNORECASE),
                re.compile(r'dd\s+if=', re.IGNORECASE),
                re.compile(r':\(\)\{.*\|.*\&\}\;:', re.IGNORECASE),
            ]
            self.blocked_imports = {'os.system', 'subprocess', 'shutil.rmtree'}
            self.python_timeout = 30
            self.blocked_paths = []
    
    def validate_path(self, path: str, require_exists: bool = False) -> tuple[bool, str]:
        """
        Validate if a path is within the sandbox.
        
        Args:
            path: Path to validate
            require_exists: If True, path must exist
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            resolved = Path(path).resolve()

            if require_exists and not resolved.exists():
                return False, f"Path does not exist: {path}"

            # Hard-block explicitly restricted files (e.g. .env)
            for blocked in self.blocked_paths:
                if resolved == blocked:
                    self.logger.warning(f"Blocked access to restricted file: {resolved}")
                    return False, "Access to this file is restricted by security policy"

            # Check if path is within any allowed path
            for allowed in self.allowed_paths:
                try:
                    resolved.relative_to(allowed)
                    return True, ""
                except ValueError:
                    continue

            return False, f"Path outside sandbox: {path}"

        except Exception as e:
            return False, f"Invalid path: {str(e)}"
    
    def validate_command(self, command: str) -> tuple[bool, str]:
        """
        Validate if a command is safe to execute.
        
        Args:
            command: Command string to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Block shell commands that would read restricted files (e.g. .env)
        _ENV_SHELL_PATTERN = re.compile(
            r'(?:^|[&|;\s])'
            r'(?:cat|type|more|less|tail|head|bat|Get-Content|gc|curl|wget|nano|vim|vi|notepad|code)'
            r'[^\n]*\.env\b',
            re.IGNORECASE,
        )
        if _ENV_SHELL_PATTERN.search(command):
            self.logger.warning(f"Blocked command attempting to read .env file: {command}")
            return False, "Command blocked by security policy"

        # Also block any command that simply references the .env filename directly
        _ENV_GENERIC_PATTERN = re.compile(r'(?:^|\s)["\']?\.env["\']?(?:\s|$)', re.IGNORECASE)
        if _ENV_GENERIC_PATTERN.search(command):
            self.logger.warning(f"Blocked command referencing .env file: {command}")
            return False, "Command blocked by security policy"

        for pattern in self.blocked_patterns:
            if pattern.search(command):
                self.logger.warning(f"Blocked dangerous command: {command}")
                return False, "Command blocked by security policy"

        return True, ""
    
    def validate_python_code(self, code: str) -> tuple[bool, str]:
        """
        Validate Python code for dangerous operations.
        
        Args:
            code: Python code to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for blocked imports
        for blocked in self.blocked_imports:
            if blocked in code:
                return False, f"Blocked import/function: {blocked}"

        # Block Python code that tries to open the .env file
        _ENV_OPEN_PATTERN = re.compile(
            r'open\s*\([^)]*["\'](?:[^"\']*/)*\.env["\'\s,)]',
            re.IGNORECASE,
        )
        if _ENV_OPEN_PATTERN.search(code):
            self.logger.warning("Blocked Python code attempting to read .env file")
            return False, "Reading .env files is blocked by security policy"

        # Also catch Path('.env').read_text() and similar
        _ENV_PATH_PATTERN = re.compile(r'["\'](?:[^"\']*/)*\.env["\']', re.IGNORECASE)
        if _ENV_PATH_PATTERN.search(code):
            self.logger.warning("Blocked Python code referencing .env file path")
            return False, "Reading .env files is blocked by security policy"

        # Check for exec/eval with user input
        dangerous_patterns = [
            r'exec\s*\(',
            r'eval\s*\(',
            r'__import__\s*\(',
            r'compile\s*\(',
            r'open\s*\([^)]*,\s*["\']w',  # Writing files
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, code):
                self.logger.warning(f"Potentially dangerous Python code detected")
                # We allow these but log them - admin decision
                break

        return True, ""
    
    def sanitize_output(self, output: str, max_length: int = 4000) -> str:
        """
        Sanitize command output for safe display.
        
        Args:
            output: Raw output string
            max_length: Maximum output length
            
        Returns:
            Sanitized output string
        """
        if len(output) > max_length:
            output = output[:max_length] + f"\n... (truncated, {len(output) - max_length} more chars)"
        
        # Remove any potential escape sequences that could be dangerous
        output = output.replace('\x1b', '[ESC]')
        
        return output


class CommandWhitelist:
    """
    Whitelist-based command validation for non-admin users.
    """
    
    def __init__(self, allowed_commands: List[str]):
        self.allowed_commands = set(cmd.lower() for cmd in allowed_commands)
    
    def is_allowed(self, command: str) -> bool:
        """Check if the command starts with an allowed command."""
        # Get the base command (first word)
        base_command = command.strip().split()[0].lower() if command.strip() else ""
        
        # Check if it's in the whitelist
        return base_command in self.allowed_commands
    
    def get_allowed_commands(self) -> Set[str]:
        """Return the set of allowed commands."""
        return self.allowed_commands.copy()
