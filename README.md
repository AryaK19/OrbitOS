# Remote MCP Control System

A comprehensive remote PC control system using FastMCP servers with Telegram as the interface. Control your PC remotely through secure, authenticated commands.

## 🚀 Features

- **Telegram Integration** - Control your PC via Telegram bot
- **Shell Commands** - Run any shell command remotely
- **File Operations** - Read, write, list, and manage files
- **Python Execution** - Execute Python code on your PC
- **App Launcher** - Launch applications remotely
- **System Monitoring** - CPU, memory, disk, and process info
- **Security** - User whitelist, permission levels, sandboxing
- **Extensible** - Plugin system for adding new MCP modules
- **LangGraph Integration** - Utilizes LangGraph for advanced agentic workflows and state management.

## 📋 Requirements

- Python 3.10+ (auto-installed by uv)
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js (for OpenCode CLI)
- Telegram account
- Windows / Linux / macOS

## 🛠️ Quick Setup

### 1. Create a Telegram Bot
1. Open Telegram and search for **[@BotFather](https://t.me/botfather)**.
2. Click **Start** or send `/start`.
3. Send `/newbot` to create a new bot.
4. Follow the prompts:
   - **Name**: Choose a display name (e.g., "My Remote Agent").
   - **Username**: Choose a unique username ending in `bot` (e.g., `MyRemotePC_bot`).
5. **Copy the HTTP API Token** provided by BotFather. You will need this for the `TELEGRAM_BOT_TOKEN`.

### 2. Get Your Telegram User ID
1. Search for **[@userinfobot](https://t.me/userinfobot)** on Telegram.
2. Click **Start**.
3. It will reply with your details. Copy the `Id` number (e.g., `123456789`). This is for the whitelist.

### 3. Install OpenCode CLI

OpenCode is the AI backend that powers natural language processing in the bot.

```bash
npm install -g opencode-ai
```

Verify the installation:
```bash
opencode --version
```

### 4. Get a Gemini API Key

OpenCode uses Google Gemini as the default AI provider.

1. Go to **[Google AI Studio](https://aistudio.google.com/apikey)**.
2. Click **Create API Key**.
3. Copy the key — you'll need it for `GEMINI_API_KEY` and `GOOGLE_GENERATIVE_AI_API_KEY` in your `.env`.

### 5. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here           # From step 1
TELEGRAM_USER_ID=your_user_id_here               # From step 2
WORKING_DIR=/Users/yourname                      # Default directory for agent commands
SANDBOX_ALLOWED_PATHS=/Users/yourname,/tmp       # Comma-separated dirs the agent can access
GOOGLE_GENERATIVE_AI_API_KEY=your_gemini_key     # From step 4
AGENT_PASSWORD=                                  # Optional, for non-whitelisted users
GIT_TOKEN=your_git_token_here                    # Optional, for GitHub features
```

### 5. Install Dependencies

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then sync the project:
```bash
uv sync
```

This creates a `.venv/`, installs the correct Python version, and installs all dependencies.

### 6. Run the Agent

```bash
uv run python src/main.py
```

For development with auto-restart on code changes:
```bash
uv run --group dev watchmedo auto-restart --directory=./src --directory=./config --pattern="*.py;*.yaml" --recursive -- python src/main.py
```

## 📱 Usage

Once running, message your bot in Telegram:

### Shell Commands
```
/shell dir
/shell echo Hello World
$ ipconfig
```

### File Operations
```
/files list C:\Users
/files read C:\Users\myfile.txt
/files write C:\temp\test.txt Hello World
```

### Python Execution
```
/python print("Hello!")
/python 2 + 2
>>> import math; math.pi
```

### Applications
```
/apps notepad
/apps chrome
/apps list
```

### System Info
```
/system info
/system processes
/system memory
```

## 🔒 Security

### Permission Levels

| Level | Capabilities |
|-------|-------------|
| `readonly` | View files, system info only |
| `user` | Execute commands, read/write files |
| `admin` | Full access includi