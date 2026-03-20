# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OrbitOS is a remote PC control system combining FastMCP servers, a Telegram bot interface, and an AI agent (OpenCode) for natural language task automation. Users interact via Telegram to execute shell commands, manage files, run Python code, launch apps, and monitor system resources — all with multi-user auth and sandboxing.

## Running the Project

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Configure environment
cp .env.example .env
# Set TELEGRAM_BOT_TOKEN in .env
# Configure user whitelist and settings in config/config.yaml

# Install dependencies and sync environment
uv sync

# Run
uv run python src/main.py
# or
uv run python -m src.main
```

There is no test suite, linter configuration, or build step.

## Architecture

```
Telegram User
    ↓
TelegramBridge (session mgmt, auth, command handlers)
    ↓
OpenCodeAgent (per-user AI context, model selection)
    ↓
MCPServer (FastMCP tool registration, command parsing/routing)
    ↓                    ↓
AuthManager          Sandbox
(permission check)   (path/command validation)
    ↓
ToolRegistry → Shell | Files | Apps | Python | System tools
```

**Request flow**: Telegram message → `TelegramBridge` authenticates user & manages session → `OpenCodeAgent` processes with AI context → `MCPServer.execute_command()` parses, authorizes via `AuthManager`, and routes via `CommandRouter` → appropriate tool executes within sandbox constraints → result returns up the chain.

## Key Design Decisions

- **Command shorthand syntax**: `$ command` routes to shell, `>>> code` routes to Python exec, `/shell`, `/files` etc. are explicit. Aliases defined in `router.py` (e.g., `sh`→`shell`, `py`→`python`).
- **Three permission tiers**: admin (full access), user (standard ops), readonly (read + system info). Defined in `config/permissions.yaml`, enforced by `auth.py`.
- **Per-user AI context**: `OpenCodeAgent` maintains separate conversation histories per `user_id`, capped at 6 messages for performance.
- **Coding mode state machine** in Telegram bridge: `STATE_WAITING_DIR` → `STATE_WAITING_GOAL` → `STATE_CODING` for project-focused sessions.
- **Plugin system**: `plugins/` directory exists for extending tools, but is currently empty.

## Config Files

- `config/config.yaml` — Main config: agent settings, Telegram token ref, security (whitelist, password, session expiry), sandbox rules (allowed paths, blocked commands), tool limits (timeouts, file size caps).
- `config/permissions.yaml` — Permission level definitions and capability mappings.
- `.env` — Runtime secrets (`TELEGRAM_BOT_TOKEN`, optional `GIT_TOKEN`). Config YAML supports `${VAR_NAME}` env expansion.

## Codebase Conventions

- All tools extend `BaseTool` (ABC in `src/tools/base.py`) and implement `execute(action, args) → str`.
- Tools register via `ToolRegistry` in `mcp_server.py` during initialization.
- Async throughout — uses `asyncio`, `aiofiles`, async subprocess execution.
- Logging via singleton `OrbitLogger` in `src/utils/logger.py` (console + rotating file in `logs/`).
- Sandbox validation (`src/utils/sandbox.py`) runs before every tool execution — path checks, command blocklist (regex), Python import restrictions.
