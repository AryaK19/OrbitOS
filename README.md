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

## 📋 Requirements

- Python 3.10+
- Windows (primary support), Linux/Mac (compatible)
- Telegram account

## 🛠️ Quick Setup

### 1. Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow prompts
3. Save the bot token

### 2. Get Your Telegram User ID

1. Message [@userinfobot](https://t.me/userinfobot)
2. Note your user ID number

### 3. Configure the System

Create a `.env` file in the project root:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

Or update `config/config.yaml` directly:

```yaml
telegram:
  token: "your_bot_token_here"

security:
  whitelist:
    - 123456789  # Your Telegram user ID
  
permissions:
  admin:
    - 123456789  # Your Telegram user ID
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the Agent

```bash
python -m src.main
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
| `admin` | Full access including delete, config |

### Sandboxing

- File operations restricted to allowed paths
- Dangerous commands blocked
- Python imports restricted

### Configuration

Edit `config/permissions.yaml` for fine-grained control.

## 🔌 Extending with Plugins

Create new MCP modules in the `plugins/` directory:

```python
from src.tools.base import BaseTool

class MyCustomTool(BaseTool):
    name = "custom"
    description = "My custom tool"
    actions = ["action1", "action2"]
    
    async def execute(self, action: str, args: dict) -> str:
        # Implement your tool logic
        return "Result"
```

Register in `mcp_server.py`:
```python
from plugins.my_custom_tool import MyCustomTool
self.registry.register_class(MyCustomTool)
```

## 📁 Project Structure

```
AGENT/
├── config/
│   ├── config.yaml         # Main configuration
│   └── permissions.yaml    # Permission definitions
├── src/
│   ├── main.py             # Entry point
│   ├── core/
│   │   ├── mcp_server.py   # FastMCP server
│   │   ├── router.py       # Command routing
│   │   └── auth.py         # Authentication
│   ├── bridges/
│   │   └── telegram_bridge.py
│   ├── tools/
│   │   ├── shell.py
│   │   ├── files.py
│   │   ├── apps.py
│   │   ├── python_exec.py
│   │   └── system.py
│   └── utils/
│       ├── logger.py
│       └── sandbox.py
├── plugins/                 # Extension modules
├── logs/                    # Log files
└── requirements.txt
```

## 🗺️ Roadmap

- [ ] Agent integration with LLM models
- [ ] GitHub MCP module
- [ ] Email MCP module
- [ ] Teams MCP module
- [ ] Web UI interface
- [ ] Voice commands

## ⚠️ Security Warning

This system allows remote command execution on your PC. Always:
- Keep your bot token secret
- Only whitelist trusted user IDs
- Review commands before expanding permissions
- Monitor audit logs regularly

## 📄 License

MIT License
