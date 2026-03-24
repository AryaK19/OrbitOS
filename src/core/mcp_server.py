"""
FastMCP Server for the Remote MCP Control System.
Exposes tools via the Model Context Protocol.
"""

import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastmcp import FastMCP

from ..tools import (
    ToolRegistry, 
    ShellTool, 
    FilesTool, 
    AppsTool, 
    PythonExecTool, 
    SystemTool
)
from ..utils.logger import get_logger, setup_logger
from ..utils.sandbox import Sandbox, SandboxConfig
from .auth import AuthManager
from .router import CommandRouter


class MCPServer:
    """
    FastMCP server that exposes tools for remote execution.
    Integrates with authentication and sandboxing.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.logger = get_logger()
        
        # Initialize components
        self._init_sandbox()
        self._init_auth()
        self._init_tools()
        self._init_router()
        self._init_mcp()
        
        self.logger.info("MCP Server initialized")
    
    def _init_sandbox(self):
        """Initialize the sandbox."""
        sandbox_config = self.config.get('sandbox', {})

        # Compute the absolute path of the project's .env file so it is always
        # blocked regardless of the current working directory.
        project_root = Path(__file__).resolve().parent.parent.parent
        env_file_path = str(project_root / ".env")

        self.sandbox = Sandbox(SandboxConfig(
            allowed_paths=sandbox_config.get('allowed_paths', [str(Path.home())]),
            blocked_commands=sandbox_config.get('blocked_commands', []),
            blocked_imports=sandbox_config.get('python', {}).get('blocked_imports', []),
            python_timeout=sandbox_config.get('python', {}).get('timeout_seconds', 30),
            blocked_paths=[env_file_path],
        ))
    
    def _init_auth(self):
        """Initialize authentication."""
        self.auth = AuthManager.from_config(self.config)
    
    def _init_tools(self):
        """Initialize and register tools."""
        self.registry = ToolRegistry()
        
        tools_config = self.config.get('tools', {})
        
        # Register all tools
        self.registry.register_class(
            ShellTool, 
            sandbox=self.sandbox, 
            config=tools_config.get('shell', {})
        )
        self.registry.register_class(
            FilesTool, 
            sandbox=self.sandbox, 
            config=tools_config.get('files', {})
        )
        self.registry.register_class(
            AppsTool, 
            sandbox=self.sandbox, 
            config=tools_config.get('apps', {})
        )
        self.registry.register_class(
            PythonExecTool, 
            sandbox=self.sandbox, 
            config=tools_config.get('python', {})
        )
        self.registry.register_class(
            SystemTool, 
            sandbox=self.sandbox, 
            config={}
        )
    
    def _init_router(self):
        """Initialize the command router."""
        self.router = CommandRouter()
        
        # Register tools with router
        for name, tool in self.registry.get_all().items():
            self.router.register_tool(name, tool)
    
    def _init_mcp(self):
        """Initialize the FastMCP server."""
        mcp_config = self.config.get('mcp', {})
        
        self.mcp = FastMCP(
            name=mcp_config.get('name', 'RemoteAgentMCP'),
            version=mcp_config.get('version', '1.0.0')
        )
        
        # Register MCP tools
        self._register_mcp_tools()
    
    def _register_mcp_tools(self):
        """Register tools with the FastMCP server."""
        
        @self.mcp.tool()
        async def run_shell(command: str, cwd: str = None, timeout: int = 60) -> str:
            """Execute a shell command on the local system."""
            tool = self.registry.get('shell')
            return await tool.execute('run', {
                'command': command,
                'cwd': cwd,
                'timeout': timeout
            })
        
        @self.mcp.tool()
        async def read_file(path: str) -> str:
            """Read the contents of a file."""
            tool = self.registry.get('files')
            return await tool.execute('read', {'path': path})
        
        @self.mcp.tool()
        async def write_file(path: str, content: str) -> str:
            """Write content to a file."""
            tool = self.registry.get('files')
            return await tool.execute('write', {'path': path, 'content': content})
        
        @self.mcp.tool()
        async def list_directory(path: str = '.') -> str:
            """List contents of a directory."""
            tool = self.registry.get('files')
            return await tool.execute('list', {'path': path})
        
        @self.mcp.tool()
        async def run_python(code: str) -> str:
            """Execute Python code."""
            tool = self.registry.get('python')
            return await tool.execute('execute', {'code': code})
        
        @self.mcp.tool()
        async def launch_app(app_name: str) -> str:
            """Launch an application."""
            tool = self.registry.get('apps')
            return await tool.execute('launch', {'app': app_name})
        
        @self.mcp.tool()
        async def get_system_info() -> str:
            """Get system information including CPU, memory, and disk usage."""
            tool = self.registry.get('system')
            return await tool.execute('info', {})
        
        @self.mcp.tool()
        async def list_processes(limit: int = 20) -> str:
            """List running processes sorted by CPU usage."""
            tool = self.registry.get('system')
            return await tool.execute('processes', {'limit': limit})
    
    async def execute_command(
        self, 
        text: str, 
        user_id: int, 
        username: str
    ) -> str:
        """
        Execute a command from a user.
        Handles authentication and routing.
        
        Args:
            text: Command text
            user_id: User's ID for auth
            username: User's display name
            
        Returns:
            Result string
        """
        # Parse command
        command = self.router.parse_command(text)
        
        if not command:
            return "❓ Unrecognized command format. Use `/help` for available commands."
        
        # Get required capability for tool
        tool = self.registry.get(command.tool)
        if tool:
            capability = tool.capabilities_required[0] if tool.capabilities_required else 'shell_execute'
        else:
            capability = 'shell_execute'
        
        # Authorize
        authorized, error = self.auth.authorize(user_id, username, capability)
        if not authorized:
            return f"🚫 {error}"
        
        # Execute
        result = await self.router.route(command)
        
        if result.success:
            return result.output
        else:
            return f"❌ Error: {result.error}"
    
    def get_mcp(self) -> FastMCP:
        """Get the FastMCP instance."""
        return self.mcp
    
    async def run_mcp(self):
        """Run the MCP server."""
        mcp_config = self.config.get('mcp', {})
        host = mcp_config.get('host', 'localhost')
        port = mcp_config.get('port', 8765)
        
        self.logger.info(f"Starting MCP server on {host}:{port}")
        await self.mcp.run()
