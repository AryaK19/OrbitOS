"""
Sandbox utility for the Remote MCP Control System.
Provides path and command sandboxing for security.
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Set
from dataclasses import dataclass

from .logger import get_logger


@dataclass
class SandboxConfig:
    """Configuration for the sandbox."""
    allowed_paths: List[str]
    blocked_commands: List[str]
    blocked_imports: List[str]
    python_timeout: int = 30


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
        else:
            # Default safe configuration
            self.allowed_paths = [Path.home().resolve()]
            self.blocked_patterns = [
                re.compile(r'rm\s+-rf\s+/', re.IGNORECASE),
                re.compile(r'format\s+[a-z]:', re.IGNORECASE),
                re.compile(r'del\s+/s\s+/q\s+[a-z]:', re.IGNORECASE),
                re.compile(r'shutdown', re.IGNORECASE),
                re.compile(r'restart', re.IGNORECASE),
            ]
            self.blocked_imports = {'os.system', 'subprocess', 'shutil.rmtree'}
            self.python_timeout = 30
    
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
        for pattern in self.blocked_patterns:
            if pattern.search(command):
                self.logger.warning(f"Blocked dangerous command: {command}")
                return False, f"Command blocked by security policy"
        
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
