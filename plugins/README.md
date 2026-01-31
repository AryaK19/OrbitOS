# Plugins Directory

This directory is for extending the Remote MCP Control System with additional modules.

## Creating a Plugin

1. Create a new Python file (e.g., `github_mcp.py`)
2. Inherit from `BaseTool`
3. Implement the `execute` method
4. Register in `mcp_server.py`

## Example Plugin Template

```python
"""
Example MCP Plugin
"""

from src.tools.base import BaseTool
from typing import Any, Dict, Optional


class ExampleTool(BaseTool):
    """
    Example tool plugin.
    """
    
    name = "example"
    description = "Example plugin tool"
    actions = ["action1", "action2"]
    capabilities_required = ["custom_capability"]
    
    def __init__(self, sandbox=None, config: Optional[dict] = None):
        super().__init__(sandbox, config)
    
    async def execute(self, action: str, args: Dict[str, Any]) -> str:
        """Execute the tool action."""
        
        if action == "action1":
            return await self._action1(args)
        elif action == "action2":
            return await self._action2(args)
        else:
            return f"Unknown action: {action}"
    
    async def _action1(self, args: Dict) -> str:
        """Implement action1."""
        return "Action 1 result"
    
    async def _action2(self, args: Dict) -> str:
        """Implement action2."""
        return "Action 2 result"
```

## Planned Plugins

- `github_mcp.py` - GitHub operations (issues, PRs, commits)
- `email_mcp.py` - Email reading and sending
- `teams_mcp.py` - Microsoft Teams integration
- `opencode_mcp.py` - OpenCode IDE integration
- `browser_mcp.py` - Browser automation
