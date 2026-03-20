"""
Main entry point for the Remote MCP Control System.
Starts the MCP server, OpenCode Agent, and Telegram bot.
"""

import asyncio
import os
import sys
import signal
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.mcp_server import MCPServer
from src.core.opencode_agent import OpenCodeAgent
from src.bridges.telegram_bridge import TelegramBridge
from src.utils.logger import setup_logger, get_logger


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config


def get_telegram_token(config: dict) -> str:
    """Get Telegram bot token from config or environment."""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        token = config.get('telegram', {}).get('token', '')
        if token.startswith('${') and token.endswith('}'):
            env_var = token[2:-1]
            token = os.getenv(env_var, '')
    
    if not token:
        raise ValueError(
            "Telegram bot token not found. "
            "Set TELEGRAM_BOT_TOKEN environment variable or update config.yaml"
        )
    
    return token


class RemoteAgentApp:
    """
    Main application class that orchestrates all components.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.logger = None
        self.mcp_server = None
        self.opencode_agent = None
        self.telegram_bridge = None
        self._running = False
    
    def setup(self):
        """Set up all components."""
        # Initialize logger
        logging_config = self.config.get('logging', {})
        self.logger = setup_logger(
            level=logging_config.get('level', 'INFO'),
            log_file=logging_config.get('file', 'logs/agent.log'),
            max_size_mb=logging_config.get('max_size_mb', 10),
            backup_count=logging_config.get('backup_count', 5)
        )
        
        self.logger.info("=" * 50)
        self.logger.info("Remote Agent MCP System Starting")
        self.logger.info("=" * 50)
        
        # Initialize MCP server (for raw commands)
        self.mcp_server = MCPServer(self.config)
        
        # Initialize OpenCode Agent
        agent_config = self.config.get('agent', {})
        agent_enabled = agent_config.get('enabled', True)
        
        if agent_enabled:
            try:
                self.opencode_agent = OpenCodeAgent(
                    agent_config, tool_registry=self.mcp_server.registry
                )
                self.logger.info("OrbitAgent (LangGraph) initialized ✓")
            except Exception as e:
                self.logger.warning(f"Failed to initialize OpenCode Agent: {e}")
                self.logger.info("Running in raw mode only")
                self.opencode_agent = None
        else:
            self.logger.info("OpenCode Agent disabled in config")
            self.opencode_agent = None
        
        # Initialize Telegram bridge
        token = get_telegram_token(self.config)
        self.telegram_bridge = TelegramBridge(
            mcp_server=self.mcp_server,
            token=token,
            opencode_agent=self.opencode_agent,
            agent_mode=agent_enabled and (self.opencode_agent is not None)
        )
        
        self.logger.info("All components initialized")
    
    async def run(self):
        """Run the agent."""
        self._running = True
        
        try:
            await self.telegram_bridge.start()
            
            self.logger.info("=" * 50)
            self.logger.info("🚀 Remote Agent is now LIVE!")
            self.logger.info("Send messages to your Telegram bot")
            self.logger.info("Mode: " + ("🤖 AGENT (LangGraph)" if self.opencode_agent else "⚡ RAW"))
            self.logger.info("=" * 50)
            
            while self._running:
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            self.logger.info("Received shutdown signal")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Gracefully shut down."""
        self.logger.info("Shutting down Remote Agent...")
        self._running = False
        
        if self.telegram_bridge:
            await self.telegram_bridge.stop()
        
        self.logger.info("Remote Agent stopped")
    
    def stop(self):
        """Signal to stop."""
        self._running = False


def expand_env_vars(config):
    """Recursively expand environment variables in config."""
    if isinstance(config, dict):
        return {k: expand_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        result = []
        for v in config:
            expanded = expand_env_vars(v)
            # If an env var contained commas, split into multiple list entries
            if isinstance(expanded, str) and ',' in expanded and v != expanded:
                result.extend(p.strip() for p in expanded.split(',') if p.strip())
            else:
                result.append(expanded)
        return result
    elif isinstance(config, str):
        if config.startswith('${') and config.endswith('}'):
            env_var = config[2:-1]
            val = os.getenv(env_var)
            if val is None:
                return config
            # Convert numeric strings to int (e.g. user IDs)
            if val.isdigit():
                return int(val)
            return val
        return config
    else:
        return config


async def main():
    """Main async entry point."""
    load_dotenv()
    
    try:
        config_raw = load_config()
        config = expand_env_vars(config_raw)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please create config/config.yaml")
        sys.exit(1)
    
    app = RemoteAgentApp(config)
    
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        app.stop()
    
    if sys.platform != 'win32':
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)
    
    try:
        app.setup()
        await app.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        raise


def run():
    """Synchronous entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    run()
