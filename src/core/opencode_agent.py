"""
Backward compatibility — delegates to the LangGraph-based OrbitAgent.
Existing imports of OpenCodeAgent from main.py and telegram_bridge.py
continue to work without changes.
"""

from ..agent import OrbitAgent as OpenCodeAgent

__all__ = ["OpenCodeAgent"]
