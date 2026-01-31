"""
Python code execution tool.
Execute Python code with sandboxing and output capture.
"""

import asyncio
import sys
import io
import traceback
from typing import Any, Dict, Optional
from contextlib import redirect_stdout, redirect_stderr

from .base import BaseTool


class PythonExecTool(BaseTool):
    """
    Execute Python code on the local system.
    Includes sandboxing and timeout handling.
    """
    
    name = "python"
    description = "Execute Python code"
    actions = ["execute", "run", "eval"]
    capabilities_required = ["python_execute"]
    
    def __init__(self, sandbox=None, config: Optional[dict] = None):
        super().__init__(sandbox, config)
        self.timeout = self.config.get('timeout_seconds', 30)
        self.max_output = 4000
    
    async def execute(self, action: str, args: Dict[str, Any]) -> str:
        """Execute Python code."""
        code = args.get('code', '').strip()
        
        if not code:
            return "❌ No code provided"
        
        # Validate code through sandbox
        if self.sandbox:
            is_valid, error = self.sandbox.validate_python_code(code)
            if not is_valid:
                return f"❌ {error}"
        
        self.logger.info(f"Executing Python code: {code[:100]}...")
        
        try:
            result = await asyncio.wait_for(
                self._execute_code(code),
                timeout=self.timeout
            )
            return result
        except asyncio.TimeoutError:
            return f"❌ Code execution timed out after {self.timeout}s"
        except Exception as e:
            self.logger.error(f"Python execution error: {e}")
            return f"❌ Execution error: {str(e)}"
    
    async def _execute_code(self, code: str) -> str:
        """Execute code in a controlled environment."""
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_code, code)
    
    def _run_code(self, code: str) -> str:
        """Run code and capture output."""
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        
        # Create execution namespace
        exec_globals = {
            '__builtins__': __builtins__,
            '__name__': '__main__',
        }
        
        result_value = None
        
        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                # Try to evaluate as expression first (for simple calculations)
                try:
                    result_value = eval(code, exec_globals)
                except SyntaxError:
                    # Not an expression, execute as statements
                    exec(code, exec_globals)
                    result_value = None
        except Exception as e:
            error_msg = traceback.format_exc()
            stderr_buffer.write(error_msg)
        
        # Collect outputs
        stdout_output = stdout_buffer.getvalue()
        stderr_output = stderr_buffer.getvalue()
        
        # Format result
        result_parts = []
        
        if result_value is not None:
            result_str = repr(result_value)
            if len(result_str) > self.max_output:
                result_str = result_str[:self.max_output] + "... (truncated)"
            result_parts.append(f"📊 **Result:**\n```python\n{result_str}\n```")
        
        if stdout_output:
            if len(stdout_output) > self.max_output:
                stdout_output = stdout_output[:self.max_output] + "\n... (truncated)"
            result_parts.append(f"📤 **Output:**\n```\n{stdout_output}\n```")
        
        if stderr_output:
            if len(stderr_output) > self.max_output:
                stderr_output = stderr_output[:self.max_output] + "\n... (truncated)"
            result_parts.append(f"❌ **Error:**\n```\n{stderr_output}\n```")
        
        if not result_parts:
            result_parts.append("✅ Code executed successfully (no output)")
        
        return "\n\n".join(result_parts)
