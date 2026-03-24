"""
Command router for the Remote MCP Control System.
Routes commands to appropriate tools and handles parsing.
"""

import re
import shlex
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass

from ..utils.logger import get_logger


@dataclass
class ParsedCommand:
    """Represents a parsed command."""
    tool: str
    action: str
    args: Dict[str, Any]
    raw: str


@dataclass
class CommandResult:
    """Result of a command execution."""
    success: bool
    output: str
    error: Optional[str] = None
    tool: str = ""
    action: str = ""


class CommandRouter:
    """
    Routes and parses commands to appropriate tools.
    Supports both slash commands and natural language.
    """
    
    # Command patterns for parsing
    COMMAND_PATTERNS = {
        # Slash commands: /tool action args
        'slash': re.compile(r'^/(\w+)\s*(.*)$', re.DOTALL),
        
        # Shell command shorthand: $ command
        'shell_shorthand': re.compile(r'^\$\s*(.+)$', re.DOTALL),
        
        # Python shorthand: >>> code
        'python_shorthand': re.compile(r'^>>>\s*(.+)$', re.DOTALL),
    }
    
    # Command aliases
    COMMAND_ALIASES = {
        'sh': 'shell',
        'cmd': 'shell',
        'terminal': 'shell',
        'run': 'shell',
        'py': 'python',
        'exec': 'python',
        'ls': 'files',
        'dir': 'files',
        'cat': 'files',
        'file': 'files',
        'open': 'apps',
        'launch': 'apps',
        'start': 'apps',
        'sys': 'system',
        'info': 'system',
        'status': 'system',
    }
    
    # Tool -> action mappings for simple commands
    DEFAULT_ACTIONS = {
        'shell': 'run',
        'files': 'list',
        'python': 'execute',
        'apps': 'launch',
        'system': 'info',
    }
    
    def __init__(self):
        self.logger = get_logger()
        self.tools: Dict[str, Any] = {}
    
    def register_tool(self, name: str, tool: Any):
        """Register a tool with the router."""
        self.tools[name] = tool
        self.logger.debug(f"Registered tool: {name}")
    
    def parse_command(self, text: str) -> Optional[ParsedCommand]:
        """
        Parse a command string into structured format.
        
        Args:
            text: Raw command text
            
        Returns:
            ParsedCommand or None if not a valid command
        """
        text = text.strip()
        
        if not text:
            return None
        
        # Check for shell shorthand: $ command
        shell_match = self.COMMAND_PATTERNS['shell_shorthand'].match(text)
        if shell_match:
            return ParsedCommand(
                tool='shell',
                action='run',
                args={'command': shell_match.group(1)},
                raw=text
            )
        
        # Check for Python shorthand: >>> code
        python_match = self.COMMAND_PATTERNS['python_shorthand'].match(text)
        if python_match:
            return ParsedCommand(
                tool='python',
                action='execute',
                args={'code': python_match.group(1)},
                raw=text
            )
        
        # Check for slash command: /tool [action] [args]
        slash_match = self.COMMAND_PATTERNS['slash'].match(text)
        if slash_match:
            tool_or_action = slash_match.group(1).lower()
            rest = slash_match.group(2).strip()
            
            # Resolve aliases
            tool = self.COMMAND_ALIASES.get(tool_or_action, tool_or_action)
            
            # Parse the rest based on tool
            return self._parse_tool_command(tool, rest, text)
        
        # Not a recognized command format
        return None
    
    def _parse_tool_command(
        self, 
        tool: str, 
        args_str: str, 
        raw: str
    ) -> ParsedCommand:
        """Parse command arguments based on tool type."""
        
        if tool == 'shell':
            return ParsedCommand(
                tool='shell',
                action='run',
                args={'command': args_str},
                raw=raw
            )
        
        elif tool == 'files':
            # Parse: /files <action> <path> [content]
            # Extended options:
            # /files list <path> --page 2 --limit 20 --filter "*.py"
            # /files search <path> --filter "*.pdf" --max-results 50 --timeout 3
            parts = args_str.split(maxsplit=2)
            action = parts[0] if parts else 'list'

            if action in {'list', 'search'}:
                try:
                    tokens = shlex.split(args_str)
                except ValueError:
                    tokens = args_str.split()

                action = tokens[0] if tokens else 'list'
                path = '.'
                parsed_args: Dict[str, Any] = {'path': path}
                index = 1

                while index < len(tokens):
                    token = tokens[index]

                    if not token.startswith('--') and parsed_args.get('path', '.') == '.':
                        parsed_args['path'] = token
                        index += 1
                        continue

                    if token in {'--page'} and index + 1 < len(tokens):
                        parsed_args['page'] = tokens[index + 1]
                        index += 2
                        continue
                    if token.startswith('--page='):
                        parsed_args['page'] = token.split('=', 1)[1]
                        index += 1
                        continue

                    if token in {'--limit'} and index + 1 < len(tokens):
                        parsed_args['limit'] = tokens[index + 1]
                        index += 2
                        continue
                    if token.startswith('--limit='):
                        parsed_args['limit'] = token.split('=', 1)[1]
                        index += 1
                        continue

                    if token in {'--filter', '--pattern'} and index + 1 < len(tokens):
                        parsed_args['filter'] = tokens[index + 1]
                        index += 2
                        continue
                    if token.startswith('--filter='):
                        parsed_args['filter'] = token.split('=', 1)[1]
                        index += 1
                        continue
                    if token.startswith('--pattern='):
                        parsed_args['filter'] = token.split('=', 1)[1]
                        index += 1
                        continue

                    if token in {'--max-results'} and index + 1 < len(tokens):
                        parsed_args['max_results'] = tokens[index + 1]
                        index += 2
                        continue
                    if token.startswith('--max-results='):
                        parsed_args['max_results'] = token.split('=', 1)[1]
                        index += 1
                        continue

                    if token in {'--timeout'} and index + 1 < len(tokens):
                        parsed_args['timeout_seconds'] = tokens[index + 1]
                        index += 2
                        continue
                    if token.startswith('--timeout='):
                        parsed_args['timeout_seconds'] = token.split('=', 1)[1]
                        index += 1
                        continue

                    index += 1

                return ParsedCommand(
                    tool='files',
                    action=action,
                    args=parsed_args,
                    raw=raw
                )

            path = parts[1] if len(parts) > 1 else '.'
            content = parts[2] if len(parts) > 2 else None

            return ParsedCommand(
                tool='files',
                action=action,
                args={'path': path, 'content': content},
                raw=raw
            )
        
        elif tool == 'python':
            return ParsedCommand(
                tool='python',
                action='execute',
                args={'code': args_str},
                raw=raw
            )
        
        elif tool == 'apps':
            return ParsedCommand(
                tool='apps',
                action='launch',
                args={'app': args_str},
                raw=raw
            )
        
        elif tool == 'system':
            action = args_str if args_str else 'info'
            return ParsedCommand(
                tool='system',
                action=action,
                args={},
                raw=raw
            )
        
        elif tool == 'help':
            return ParsedCommand(
                tool='help',
                action='show',
                args={'topic': args_str},
                raw=raw
            )
        
        else:
            # Generic parsing
            return ParsedCommand(
                tool=tool,
                action=self.DEFAULT_ACTIONS.get(tool, 'execute'),
                args={'input': args_str},
                raw=raw
            )
    
    async def route(self, command: ParsedCommand) -> CommandResult:
        """
        Route a parsed command to the appropriate tool.
        
        Args:
            command: Parsed command to route
            
        Returns:
            CommandResult from tool execution
        """
        tool_name = command.tool
        
        if tool_name == 'help':
            return self._handle_help(command.args.get('topic', ''))
        
        if tool_name not in self.tools:
            return CommandResult(
                success=False,
                output="",
                error=f"Unknown tool: {tool_name}",
                tool=tool_name,
                action=command.action
            )
        
        tool = self.tools[tool_name]
        
        try:
            result = await tool.execute(command.action, command.args)
            return CommandResult(
                success=True,
                output=result,
                tool=tool_name,
                action=command.action
            )
        except Exception as e:
            self.logger.error(f"Tool execution error: {e}", exc_info=True)
            return CommandResult(
                success=False,
                output="",
                error=str(e),
                tool=tool_name,
                action=command.action
            )
    
    def _handle_help(self, topic: str) -> CommandResult:
        """Generate help text."""
        help_text = """
        🤖 **Remote Agent Commands**

        **Shell Commands:**
        • `/shell <command>` - Run a shell command
        • `$ <command>` - Shorthand for shell

        **File Operations:**
        • `/files list <path> --page 1 --limit 20 --filter "*.py"` - List directory contents (paginated)
• `/files search <path> --filter "*.pdf" --max-results 50 --timeout 3` - Recursive file search
        • `/files read <path>` - Read file contents
        • `/files write <path> <content>` - Write to file
• `/files rename <path> <new_path>` - Rename file or directory
• `/files move <path> <destination>` - Move file or directory

        **Python Execution:**
        • `/python <code>` - Execute Python code
        • `>>> <code>` - Shorthand for Python

        **Applications:**
        • `/apps <app_name>` - Launch an application

        **System:**
        • `/system info` - System information
        • `/system processes` - List processes

        **Help:**
        • `/help` - Show this help
        """
        return CommandResult(
            success=True,
            output=help_text,
            tool='help',
            action='show'
        )
    
    def get_available_tools(self) -> List[str]:
        """Get list of registered tools."""
        return list(self.tools.keys())
