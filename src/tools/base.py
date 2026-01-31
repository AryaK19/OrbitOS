"""
Base tool class and registry for the Remote MCP Control System.
All tools inherit from BaseTool.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass

from ..utils.logger import get_logger


@dataclass
class ToolInfo:
    """Information about a registered tool."""
    name: str
    description: str
    actions: List[str]
    capabilities_required: List[str]


class BaseTool(ABC):
    """
    Abstract base class for all tools.
    Tools implement specific functionality that can be invoked via MCP.
    """
    
    # Override in subclasses
    name: str = "base"
    description: str = "Base tool"
    actions: List[str] = []
    capabilities_required: List[str] = []
    
    def __init__(self, sandbox=None, config: Optional[dict] = None):
        self.logger = get_logger()
        self.sandbox = sandbox
        self.config = config or {}
    
    @abstractmethod
    async def execute(self, action: str, args: Dict[str, Any]) -> str:
        """
        Execute a tool action.
        
        Args:
            action: The action to perform
            args: Arguments for the action
            
        Returns:
            String result of the action
        """
        pass
    
    def get_info(self) -> ToolInfo:
        """Get information about this tool."""
        return ToolInfo(
            name=self.name,
            description=self.description,
            actions=self.actions,
            capabilities_required=self.capabilities_required
        )
    
    def _validate_action(self, action: str) -> bool:
        """Validate that the action is supported."""
        return action in self.actions


class ToolRegistry:
    """
    Registry for managing available tools.
    Supports dynamic registration and discovery.
    """
    
    def __init__(self):
        self.logger = get_logger()
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool):
        """Register a tool instance."""
        self._tools[tool.name] = tool
        self.logger.info(f"Registered tool: {tool.name}")
    
    def register_class(
        self, 
        tool_class: Type[BaseTool], 
        sandbox=None,
        config: Optional[dict] = None
    ):
        """Register a tool by class, instantiating it."""
        tool = tool_class(sandbox=sandbox, config=config)
        self.register(tool)
        return tool
    
    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def get_all(self) -> Dict[str, BaseTool]:
        """Get all registered tools."""
        return self._tools.copy()
    
    def list_tools(self) -> List[ToolInfo]:
        """Get information about all registered tools."""
        return [tool.get_info() for tool in self._tools.values()]
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool by name."""
        if name in self._tools:
            del self._tools[name]
            self.logger.info(f"Unregistered tool: {name}")
            return True
        return False
