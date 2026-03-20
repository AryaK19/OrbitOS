"""
OpenCode Agent Bridge for the Remote MCP Control System.
Simplified prompts for faster response. Direct file search for simple requests.
"""

import asyncio
import os
import glob
import re
from typing import Optional, List, Dict
from pathlib import Path
from dataclasses import dataclass, field

from ..utils.logger import get_logger, AuditLogger


@dataclass
class ConversationMessage:
    """A message in the conversation."""
    role: str
    content: str


@dataclass 
class UserContext:
    """Conversation context per user."""
    messages: List[ConversationMessage] = field(default_factory=list)
    max_messages: int = 6  # Reduced for shorter prompts
    
    def add_user_message(self, content: str):
        self.messages.append(ConversationMessage(role="user", content=content))
        self._trim()
    
    def add_assistant_message(self, content: str):
        self.messages.append(ConversationMessage(role="assistant", content=content))
        self._trim()
    
    def _trim(self):
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
    
    def get_history_prompt(self) -> str:
        """Get compact history."""
        if len(self.messages) <= 1:
            return ""
        
        parts = []
        for msg in self.messages[:-1]:
            role = "U" if msg.role == "user" else "A"
            # Very compact - just 100 chars
            content = msg.content[:100].replace('\n', ' ')
            parts.append(f"{role}: {content}")
        
        return "Context:\n" + "\n".join(parts[-3:]) + "\n\n"  # Only last 3
    
    def clear(self):
        self.messages = []


class OpenCodeAgent:
    """
    Bridge to OpenCode CLI. Simplified for speed.
    Uses direct file search for file requests.
    Supports per-user model selection.
    """
    
    # Available models from opencode - use full provider/model format
    AVAILABLE_MODELS = [
        # Antigravity models
        ("google/antigravity-gemini-3-pro", "Antigravity Gemini 3 Pro"),
        ("google/antigravity-gemini-3-flash", "Antigravity Gemini 3 Flash"),
        ("google/antigravity-claude-sonnet-4-5", "Antigravity Claude 4.5"),
        ("google/antigravity-claude-sonnet-4-5-thinking", "Antigravity Claude 4.5 Thinking"),
        # Google models
        ("google/gemini-2.5-flash", "Gemini 2.5 Flash"),
        ("google/gemini-2.5-pro", "Gemini 2.5 Pro"),
        ("google/gemini-3-flash-preview", "Gemini 3 Flash"),
        ("google/gemini-3-pro-preview", "Gemini 3 Pro"),
        # Copilot models
        ("copilot/claude-sonnet-4", "Copilot Claude Sonnet 4"),
        ("copilot/gemini-2.5-pro", "Copilot Gemini 2.5 Pro"),
        ("copilot/gpt-4.1", "Copilot GPT-4.1"),
        ("copilot/gpt-4o", "Copilot GPT-4o"),
        ("copilot/o3-mini", "Copilot o3-mini"),
        ("copilot/o4-mini", "Copilot o4-mini"),
        # GitHub Copilot models
        ("github-copilot/claude-sonnet-4", "GH Claude Sonnet 4"),
        ("github-copilot/claude-sonnet-4.5", "GH Claude Sonnet 4.5"),
        ("github-copilot/claude-opus-4.5", "GH Claude Opus 4.5"),
        ("github-copilot/claude-sonnet-4.6", "GH Claude Sonnet 4.6"),
        ("github-copilot/claude-haiku-4.5", "GH Claude Haiku 4.5"),
        ("github-copilot/gpt-4o", "GH GPT-4o"),
        ("github-copilot/gpt-5", "GH GPT-5"),
        ("github-copilot/gpt-5-mini", "GH GPT-5 Mini"),
        ("github-copilot/gpt-5.1", "GH GPT-5.1"),
        ("github-copilot/gpt-5.2", "GH GPT-5.2"),
        ("github-copilot/gemini-2.5-pro", "GH Gemini 2.5 Pro"),
        ("github-copilot/gemini-3-flash-preview", "GH Gemini 3 Flash"),
        ("github-copilot/grok-code-fast-1", "GH Grok Code Fast"),
    ]
    
    DEFAULT_MODEL = "google/antigravity-gemini-3-flash"
    
    # Common locations to search for files (order matters — try most likely first)
    SEARCH_PATHS = [
        Path.home() / "Desktop",
        Path.home() / "OneDrive" / "Desktop",
        Path.home() / "OneDrive - Personal" / "Desktop",
        Path.home() / "Documents",
        Path.home() / "OneDrive" / "Documents",
        Path.home() / "OneDrive - Personal" / "Documents",
        Path.home() / "Downloads",
        Path.home() / "Pictures",
        Path.home() / "OneDrive",
        Path.home() / "OneDrive - Personal",
        Path.home(),
    ]
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.logger = get_logger()
        self.audit = AuditLogger()
        
        self.timeout = self.config.get('timeout', 180)  # 3 min for MCP operations
        self.working_dir = self.config.get('working_dir', str(Path.home()))
        self.default_model = self.config.get('model', self.DEFAULT_MODEL)
        
        self.contexts: Dict[int, UserContext] = {}
        self.user_models: Dict[int, str] = {}  # Per-user model selection
        
        self.logger.info("OpenCode Agent initialized")
    
    def get_available_models(self) -> List[tuple]:
        """Get list of available models."""
        return self.AVAILABLE_MODELS
    
    def set_user_model(self, user_id: int, model_id: str) -> bool:
        """Set model for a user. Returns True if valid model."""
        valid_ids = [m[0] for m in self.AVAILABLE_MODELS]
        if model_id in valid_ids:
            self.user_models[user_id] = model_id
            self.logger.info(f"User {user_id} switched to model: {model_id}")
            return True
        return False
    
    def get_user_model(self, user_id: int) -> str:
        """Get current model for user."""
        return self.user_models.get(user_id, self.default_model)
    
    def _get_context(self, user_id: int) -> UserContext:
        if user_id not in self.contexts:
            self.contexts[user_id] = UserContext()
        return self.contexts[user_id]
        return self.contexts[user_id]
    
    async def process(
        self, 
        message: str, 
        user_id: int,
        username: str = "user",
        working_dir: str = None,
        system_context: str = None
    ) -> str:
        """Process a message via OpenCode."""
        self.logger.info(f"Processing: {message[:50]}...")
        
        context = self._get_context(user_id)
        
        # Let OpenCode handle all requests - it's smarter than direct search
        context.add_user_message(message)
        
        try:
            prompt = self._build_prompt(message, context, system_context)
            result = await self._run_opencode(prompt, working_dir or self.working_dir, user_id)
            
            context.add_assistant_message(result)
            
            self.audit.log_command(
                user_id=user_id,
                username=username,
                command=f"opencode: {message[:30]}",
                tool="opencode_agent",
                result=result[:50] if result else "",
                success=True
            )
            
            return result
            
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout for user {user_id}")
            return "⏱️ Timeout. Try a simpler request."
            
        except Exception as e:
            self.logger.error(f"Error: {e}")
            return f"⚠️ Error: {str(e)}"
    
    def _extract_file_search(self, message: str) -> Optional[dict]:
        """Extract file search parameters from message."""
        msg_lower = message.lower()
        
        # Check if it's a file request
        file_keywords = ['send', 'find', 'get', 'show', 'where is', 'locate']
        if not any(kw in msg_lower for kw in file_keywords):
            return None
        
        # Extract filename patterns
        # Look for quoted filenames
        quoted = re.findall(r'["\']([^"\']+)["\']', message)
        if quoted:
            filename = quoted[0]
        else:
            # Look for common patterns like "filename.ext"
            file_pattern = re.search(r'([a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+)', message)
            if file_pattern:
                filename = file_pattern.group(1)
            else:
                # Look for "named X" or "called X"
                named = re.search(r'(?:named?|called?)\s+([a-zA-Z0-9_\-\.\s]+?)(?:\s+in|\s+from|$)', message, re.I)
                if named:
                    filename = named.group(1).strip()
                else:
                    return None
        
        # Extract location
        location = None
        loc_patterns = [
            (r'(?:in|from|inside|on)\s+(?:my\s+)?(?:one\s*drive\s+)?desktop', 'Desktop'),
            (r'(?:in|from|inside)\s+(?:my\s+)?(?:one\s*drive\s+)?documents?', 'Documents'),
            (r'(?:in|from|inside)\s+(?:my\s+)?downloads?', 'Downloads'),
            (r'(?:in|from|inside)\s+(?:my\s+)?pictures?', 'Pictures'),
            (r'(?:in|from|inside)\s+(?:the\s+)?study', 'Documents/Study'),
            (r'one\s*drive', 'OneDrive'),
        ]
        
        for pattern, loc in loc_patterns:
            if re.search(pattern, msg_lower):
                location = loc
                break
        
        return {'filename': filename, 'location': location}
    
    def _search_files(self, filename: str, location: str = None) -> List[str]:
        """Search for files directly. Auto-expands to alternate paths if primary location missing."""
        found = []
        filename_lower = filename.lower().replace(' ', '*')
        
        # Add wildcards if not present
        if '*' not in filename_lower:
            search_pattern = f"*{filename_lower}*"
        else:
            search_pattern = filename_lower
        
        # Determine search paths — expand to OneDrive equivalents automatically
        if location:
            # Build candidate paths: standard + OneDrive variants
            candidates = [
                Path.home() / location,
                Path.home() / "OneDrive" / location,
                Path.home() / "OneDrive - Personal" / location,
            ]
            # For "Desktop" specifically also try OneDrive root children
            if location.lower() == "onedrive":
                candidates = [
                    Path.home() / "OneDrive",
                    Path.home() / "OneDrive - Personal",
                ]
            paths = [p for p in candidates if p.exists()]
            # If none found, fall back to full default search
            if not paths:
                self.logger.info(
                    f"Location '{location}' not found at standard path — "
                    f"falling back to full search across all known paths"
                )
                paths = [p for p in self.SEARCH_PATHS if p.exists()]
        else:
            paths = [p for p in self.SEARCH_PATHS if p.exists()]
        
        for base_path in paths:
            # Search recursively (limited depth)
            try:
                for root, dirs, files in os.walk(base_path):
                    # Limit depth
                    depth = len(Path(root).relative_to(base_path).parts)
                    if depth > 3:
                        dirs.clear()
                        continue
                    
                    for file in files:
                        if self._matches_pattern(file.lower(), search_pattern):
                            full_path = os.path.join(root, file)
                            if full_path not in found:
                                found.append(full_path)
                    
                    if len(found) >= 15:
                        return found
                        
            except PermissionError:
                continue
        
        return found
    
    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches pattern."""
        import fnmatch
        # Also check if pattern is substring
        clean_pattern = pattern.replace('*', '')
        return fnmatch.fnmatch(filename, pattern) or clean_pattern in filename
    
    def _build_prompt(self, message: str, context: UserContext, system_context: str = None) -> str:
        """Build a prompt that encourages autonomous searching before asking the user."""
        history = context.get_history_prompt()
        
        prompt_parts = []
        if system_context:
            prompt_parts.append(f"Context: {system_context}")
            
        prompt_parts.append(history)
        prompt_parts.append(f"Request: {message}")
        prompt_parts.append(
            "\nIMPORTANT: Before asking the user any questions, exhaustively try all likely "
            "locations yourself. On Windows, if a standard path like Desktop does not exist, "
            "automatically check OneDrive\\Desktop, OneDrive - Personal\\Desktop, and other "
            "OneDrive variants. Search broadly and silently across all known paths first. "
            "Only ask the user if every reasonable search has been exhausted. "
            "IMPORTANT: List the FULL ABSOLUTE PATHS of matching files, one per line. "
            "Start each path with the drive letter (e.g., C:\\\\Users\\\\...). "
            "If no files found, explain why."
        )
        prompt_parts.append("\nExecute the request. Be concise in your response.")
        
        return "\n".join(prompt_parts)
    
    async def _run_opencode(self, prompt: str, cwd: str, user_id: int = None) -> str:
        """Run OpenCode CLI and stream output in real-time."""
        # Escape for shell
        escaped = prompt.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', '')
        
        # Get model for this user
        model = self.get_user_model(user_id) if user_id else self.default_model
        
        if model:
            cmd = f'opencode run -m {model} "{escaped}"'
        else:
            cmd = f'opencode run "{escaped}"'
        
        self.logger.info(f"Using model: {model}")
        self.logger.debug(f"Command: {cmd[:100]}...")
        
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            shell=True
        )
        
        output_lines = []
        
        try:
            # Read stdout line by line in real-time
            async def read_stream(stream, prefix):
                lines = []
                while True:
                    line = await asyncio.wait_for(stream.readline(), timeout=self.timeout)
                    if not line:
                        break
                    text = line.decode('utf-8', errors='replace').rstrip()
                    if text:
                        # Log intermediate steps (filter out noise)
                        if not any(skip in text for skip in ['WARN', 'DEBUG', 'tokens']):
                            self.logger.info(f"[OpenCode] {text[:100]}")
                        lines.append(text)
                return lines
            
            # Read both streams concurrently
            stdout_task = asyncio.create_task(read_stream(process.stdout, "OUT"))
            stderr_task = asyncio.create_task(read_stream(process.stderr, "ERR"))
            
            stdout_lines, stderr_lines = await asyncio.gather(stdout_task, stderr_task)
            await process.wait()
            
            output_lines = stdout_lines
            
            # Clean the output
            stdout_text = '\n'.join(output_lines)
            output = self._clean_output(stdout_text)
            
            # If stdout empty, try stderr
            if not output and stderr_lines:
                stderr_text = '\n'.join(stderr_lines)
                stderr_clean = self._clean_output(stderr_text)
                if stderr_clean and not stderr_clean.startswith('WARN'):
                    output = stderr_clean
            
            if not output:
                self.logger.warning("OpenCode returned empty output")
                return "✅ Done (no output returned)"
            
            return output
            
        except asyncio.TimeoutError:
            process.kill()
            raise
    
    def _clean_output(self, output: str) -> str:
        """Remove log/noise lines from output but keep actual content."""
        if not output:
            return ""
        
        lines = output.split('\n')
        cleaned = []
        
        for line in lines:
            stripped = line.strip()
            
            # Skip common noise patterns
            if stripped.startswith('INFO '):
                continue
            if stripped.startswith('WARN '):
                continue
            if stripped.startswith('DEBUG '):
                continue
            if 'models.dev' in stripped:
                continue
            if 'refreshing' in stripped and 'service=' in stripped:
                continue
            if stripped.startswith('At C:\\') and 'npm\\' in stripped:
                continue
            if stripped.startswith('+') and 'node$exe' in stripped:
                continue
            
            # Skip empty lines at start
            if not cleaned and not stripped:
                continue
                
            cleaned.append(line)
        
        # Remove trailing empty lines
        while cleaned and not cleaned[-1].strip():
            cleaned.pop()
        
        return '\n'.join(cleaned).strip()
    
    def clear_context(self, user_id: int):
        """Clear user context."""
        if user_id in self.contexts:
            self.contexts[user_id].clear()
            self.logger.info(f"Cleared context for {user_id}")
