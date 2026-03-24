"""
OrbitAgent — LangGraph ReAct agent for OrbitOS.
Replaces the OpenCode CLI subprocess with direct LLM API calls and tool use.
"""

import asyncio
import time
from typing import Optional
from dataclasses import dataclass, field

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langgraph.prebuilt import create_react_agent

from ..tools.base import ToolRegistry
from ..utils.logger import get_logger, AuditLogger
from .providers import create_llm, AVAILABLE_MODELS
from .tools import create_all_tools
from .prompts import SYSTEM_PROMPT


@dataclass
class UserContext:
    """Per-user conversation context using LangChain message types."""

    messages: list[BaseMessage] = field(default_factory=list)
    max_messages: int = 20

    def add_user_message(self, content: str):
        self.messages.append(HumanMessage(content=content))
        self._trim()

    def add_turn(self, new_messages: list[BaseMessage]):
        """Add all messages from an agent turn (AI + tool calls + tool results)."""
        self.messages.extend(new_messages)
        self._trim()

    def _trim(self):
        if len(self.messages) > self.max_messages:
            trimmed = self.messages[-self.max_messages:]
            # Re-anchor to the first HumanMessage so we never start with a
            # dangling AIMessage(tool_calls), which Gemini rejects as
            # INVALID_ARGUMENT ("function call turn must follow user/tool turn").
            for i, msg in enumerate(trimmed):
                if isinstance(msg, HumanMessage):
                    self.messages = trimmed[i:]
                    return
            # No HumanMessage found in the trimmed window — discard all to
            # avoid sending a corrupted history.
            self.messages = []

    def get_messages(self) -> list[BaseMessage]:
        return list(self.messages)

    def clear(self):
        self.messages = []


class OrbitAgent:
    """
    LangGraph-based agent for OrbitOS.
    Provides the same process() interface as the old OpenCodeAgent.
    """

    def __init__(self, config: dict, tool_registry: ToolRegistry):
        self.config = config
        self.logger = get_logger()
        self.audit = AuditLogger()

        self.timeout = config.get("timeout", 120)
        self.default_model = config.get("model", "google/gemini-2.5-flash")
        self.max_iterations = config.get("max_tool_iterations", 10)
        self.temperature = config.get("temperature", 0.1)
        self.max_context_messages = config.get("max_context_messages", 20)

        # Wrap OrbitOS tools as LangChain tools
        self.tools = create_all_tools(tool_registry)
        tool_names = [t.name for t in self.tools]
        self.logger.info(f"LangGraph tools registered: {tool_names}")

        # Per-user state
        self.contexts: dict[int, UserContext] = {}
        self.user_models: dict[int, str] = {}

        # Cache LLM instances per model_id to avoid re-creating
        self._llm_cache: dict = {}

        self.logger.info(
            f"OrbitAgent initialized | model={self.default_model} | "
            f"timeout={self.timeout}s | max_iterations={self.max_iterations} | "
            f"tools={len(self.tools)}"
        )

    # ── Model selection (same interface as old OpenCodeAgent) ──

    def get_available_models(self) -> list[tuple]:
        return AVAILABLE_MODELS

    def set_user_model(self, user_id: int, model_id: str) -> bool:
        valid_ids = [m[0] for m in AVAILABLE_MODELS]
        if model_id in valid_ids:
            self.user_models[user_id] = model_id
            # Invalidate cached LLM for this user's old model
            self.logger.info(f"User {user_id} switched to model: {model_id}")
            return True
        return False

    def get_user_model(self, user_id: int) -> str:
        return self.user_models.get(user_id, self.default_model)

    # ── Context management ──

    def _get_context(self, user_id: int) -> UserContext:
        if user_id not in self.contexts:
            self.contexts[user_id] = UserContext(max_messages=self.max_context_messages)
        return self.contexts[user_id]

    def clear_context(self, user_id: int):
        if user_id in self.contexts:
            self.contexts[user_id].clear()
            self.logger.info(f"Cleared context for {user_id}")

    # ── LLM creation with caching ──

    def _get_or_create_llm(self, model_id: str):
        if model_id not in self._llm_cache:
            self.logger.info(f"Creating LLM instance for model: {model_id}")
            self._llm_cache[model_id] = create_llm(
                model_id=model_id,
                temperature=self.temperature,
                timeout=self.timeout,
            )
        return self._llm_cache[model_id]

    # ── Main process() method ──

    async def process(
        self,
        message: str,
        user_id: int,
        username: str = "user",
        working_dir: str = None,
        system_context: str = None,
    ) -> str:
        """Process a user message through the LangGraph agent.

        Same signature as the old OpenCodeAgent.process() for backward compatibility.
        """
        model_id = self.get_user_model(user_id)
        self.logger.info(
            f"[user={user_id}] Processing: {message[:80]}... | "
            f"model={model_id} | timeout={self.timeout}s"
        )
        start_time = time.monotonic()

        context = self._get_context(user_id)
        context.add_user_message(message)

        try:
            # Build system prompt with optional context
            sys_prompt = SYSTEM_PROMPT
            if system_context:
                sys_prompt += f"\n\nAdditional context: {system_context}"
            if working_dir:
                sys_prompt += f"\n\nUser's current working directory: {working_dir}"

            # Get or create LLM
            llm = self._get_or_create_llm(model_id)

            # Create the ReAct agent graph
            graph = create_react_agent(
                llm,
                self.tools,
                prompt=sys_prompt,
            )

            # Invoke with timeout
            self.logger.info(f"[user={user_id}] Invoking LangGraph agent...")
            result = await asyncio.wait_for(
                graph.ainvoke(
                    {"messages": context.get_messages()},
                    config={"recursion_limit": self.max_iterations * 2 + 1},
                ),
                timeout=self.timeout,
            )

            elapsed = time.monotonic() - start_time

            # Extract the new messages from this turn (everything after our input)
            all_messages = result.get("messages", [])
            input_count = len(context.get_messages())
            new_messages = all_messages[input_count:]

            # Find the final AI response
            response_text = self._extract_response(new_messages)

            # Store the turn in context
            context.add_turn(new_messages)

            self.logger.info(
                f"[user={user_id}] Completed in {elapsed:.1f}s | "
                f"response_len={len(response_text)} | "
                f"tool_calls={self._count_tool_calls(new_messages)}"
            )

            self.audit.log_command(
                user_id=user_id,
                username=username,
                command=f"agent: {message[:30]}",
                tool="langgraph_agent",
                result=response_text[:50] if response_text else "",
                success=True,
            )

            return response_text

        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start_time
            self.logger.error(
                f"[user={user_id}] TIMEOUT after {elapsed:.1f}s | model={model_id} | "
                f"msg={message[:60]}... | LLM API did not respond within {self.timeout}s"
            )
            return (
                f"⏱️ Timeout after {int(elapsed)}s. "
                f"The AI model ({model_id}) took too long. "
                f"Try a simpler request or switch models with /models."
            )

        except Exception as e:
            elapsed = time.monotonic() - start_time
            error_str = str(e)
            category = self._classify_error(error_str)

            # Gemini rejects histories where a tool-call turn doesn't
            # immediately follow a user or tool-response turn.  Clear the
            # corrupted context so the next message works cleanly.
            if "function call turn" in error_str.lower() or (
                "invalid_argument" in error_str.lower()
                and "function" in error_str.lower()
            ):
                context.clear()
                self.logger.warning(
                    f"[user={user_id}] Cleared corrupted context after "
                    f"INVALID_ARGUMENT | model={model_id}"
                )
                return (
                    "⚠️ Conversation context was reset due to a message-ordering "
                    "error with the AI model. Please resend your message."
                )

            self.logger.error(
                f"[user={user_id}] {category} after {elapsed:.1f}s | "
                f"model={model_id} | error={error_str}",
                exc_info=True,
            )
            return f"⚠️ Error ({category}): {error_str}"

    # ── Helpers ──

    def _extract_response(self, messages: list[BaseMessage]) -> str:
        """Extract the final text response from agent messages."""
        # Walk backwards to find the last AIMessage with text content
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                # content can be a string or a list of content blocks
                if isinstance(msg.content, str):
                    return msg.content
                elif isinstance(msg.content, list):
                    # Extract text parts from content blocks
                    text_parts = []
                    for block in msg.content:
                        if isinstance(block, str):
                            text_parts.append(block)
                        elif isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block["text"])
                    if text_parts:
                        return "\n".join(text_parts)
        return "✅ Done (no output returned)"

    def _count_tool_calls(self, messages: list[BaseMessage]) -> int:
        """Count tool calls in a message sequence."""
        count = 0
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                count += len(msg.tool_calls)
        return count

    @staticmethod
    def _classify_error(error_str: str) -> str:
        """Classify an error for logging and user display."""
        lower = error_str.lower()
        if "rate" in lower or "429" in lower or "quota" in lower:
            return "RATE_LIMIT"
        if "auth" in lower or "401" in lower or "403" in lower or "api key" in lower:
            return "AUTH_ERROR"
        if "connection" in lower or "network" in lower or "dns" in lower:
            return "NETWORK_ERROR"
        if "not found" in lower or "no such" in lower:
            return "NOT_FOUND"
        if "recursion" in lower or "iteration" in lower:
            return "MAX_ITERATIONS"
        return "UNKNOWN_ERROR"
