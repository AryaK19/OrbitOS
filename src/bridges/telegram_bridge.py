"""
Telegram Bridge for the Remote MCP Control System.
Connects Telegram bot interface to OpenCode Agent.
Includes session management for conversation context.
"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from telegram import Update, BotCommand, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from ..core.mcp_server import MCPServer
from ..core.opencode_agent import OpenCodeAgent
from ..utils.logger import get_logger, AuditLogger


class TelegramBridge:
    """
    Bridge between Telegram bot and OpenCode Agent.
    Includes session management for conversation context.
    """
    
    # File extensions that can be sent
    ALLOWED_FILE_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp',
        '.pdf', '.txt', '.md', '.json', '.yaml', '.yml', '.xml',
        '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.go', '.rs',
        '.html', '.css', '.sql',
        '.zip', '.rar', '.7z', '.tar', '.gz',
        '.log', '.csv', '.xlsx', '.docx', '.pptx'
    }
    
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    def __init__(
        self, 
        mcp_server: MCPServer, 
        token: str,
        opencode_agent: Optional[OpenCodeAgent] = None,
        agent_mode: bool = True
    ):
        self.mcp = mcp_server
        self.token = token
        self.agent = opencode_agent
        self.agent_mode = agent_mode and (opencode_agent is not None)
        self.logger = get_logger()
        self.audit = AuditLogger()
        
        # Session tracking per user
        self.sessions: dict = {}  # user_id -> session_info
        
        # Build application
        self.app = Application.builder().token(token).build()
        self._register_handlers()
        
        self.logger.info(f"Telegram Bridge initialized (Agent mode: {self.agent_mode})")
    
    def _register_handlers(self):
        """Register message handlers."""
        # Session management commands
        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(CommandHandler("new", self._handle_new_session))
        self.app.add_handler(CommandHandler("clear", self._handle_clear))
        self.app.add_handler(CommandHandler("session", self._handle_session_info))
        self.app.add_handler(CommandHandler("history", self._handle_history))
        
        # Model selection commands
        self.app.add_handler(CommandHandler("models", self._handle_models))
        self.app.add_handler(CommandHandler("model", self._handle_set_model))
        self.app.add_handler(CallbackQueryHandler(self._handle_model_callback, pattern="^model:"))
        
        # Utility commands
        self.app.add_handler(CommandHandler("help", self._handle_help))
        self.app.add_handler(CommandHandler("send", self._handle_send_file))
        
        # Auth commands
        self.app.add_handler(CommandHandler("login", self._handle_login))
        self.app.add_handler(CommandHandler("logout", self._handle_logout))
        
        # Code Mode commands
        self.app.add_handler(CommandHandler("code", self._handle_code_mode))
        self.app.add_handler(CommandHandler("exit", self._handle_exit_code_mode))
        
        # All other messages go to OpenCode
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            self._handle_message
        ))
    
    # Session States
    STATE_NORMAL = "normal"
    STATE_WAITING_DIR = "waiting_dir"
    STATE_WAITING_GOAL = "waiting_goal"
    STATE_CODING = "coding"

    def _get_session(self, user_id: int) -> dict:
        """Get or create session for a user."""
        if user_id not in self.sessions:
            self.sessions[user_id] = {
                'started': datetime.now(),
                'message_count': 0,
                'last_activity': datetime.now(),
                'authenticated': False,
                'login_time': None,
                # /code mode state
                'mode': self.STATE_NORMAL,
                'project_dir': None,
                'project_goal': None
            }
        return self.sessions[user_id]
    
    def _update_session(self, user_id: int):
        """Update session activity."""
        session = self._get_session(user_id)
        session['message_count'] += 1
        session['last_activity'] = datetime.now()
        
    async def _handle_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /login <password>."""
        user = update.effective_user
        session = self._get_session(user.id)
        
        # Check if already authenticated and valid
        if self._is_session_valid(session):
            await update.message.reply_text("✅ You are already logged in.")
            return
            
        # Get password from args
        password = ' '.join(context.args).strip()
        if not password:
            await update.message.reply_text("usage: /login <password>")
            return
            
        if self.mcp.auth.verify_password(password):
            session['authenticated'] = True
            session['login_time'] = datetime.now()
            hours = self.mcp.config.get('security', {}).get('session_expiry_hours', 24)
            await update.message.reply_text(f"✅ Login successful. Session valid for {hours} hours.")
            self.logger.info(f"User {user.id} logged in successfully")
        else:
            await update.message.reply_text("❌ Invalid password.")
            self.logger.warning(f"Failed login attempt by user {user.id}")

    async def _handle_logout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /logout."""
        user = update.effective_user
        session = self._get_session(user.id)
        
        session['authenticated'] = False
        session['login_time'] = None
        
        await update.message.reply_text("👋 Logged out.")

    async def _handle_code_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /code - Enter specialized coding mode."""
        if not await self._check_auth(update): return
        
        user = update.effective_user
        session = self._get_session(user.id)
        
        # Reset coding state
        session['mode'] = self.STATE_WAITING_DIR
        session['project_dir'] = None
        session['project_goal'] = None
        
        # Clear context so we start fresh for this task
        if self.agent:
            self.agent.clear_context(user.id)
            
        await update.message.reply_text(
            "🚀 **Starting Coding Session**\n\n"
            "I will help you plan and execute a coding task.\n"
            "First, please enter the **project directory** (full absolute path).",
            parse_mode='Markdown'
        )

    async def _handle_exit_code_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /exit - Exit coding mode."""
        user = update.effective_user
        session = self._get_session(user.id)
        
        if session['mode'] == self.STATE_NORMAL:
            await update.message.reply_text("ℹ️ You are not in coding mode.")
            return

        session['mode'] = self.STATE_NORMAL
        session['project_dir'] = None
        session['project_goal'] = None
        
        await update.message.reply_text(
            "⏹️ **Exited Coding Mode**\n\n"
            "Returned to normal agent mode.",
            parse_mode='Markdown'
        )
    
    def _is_session_valid(self, session: dict) -> bool:
        """Check if session is authenticated and not expired."""
        if not session.get('authenticated'):
            return False
            
        login_time = session.get('login_time')
        if not login_time:
            return False
            
        expiry_hours = self.mcp.config.get('security', {}).get('session_expiry_hours', 24)
        age = datetime.now() - login_time
        
        if age.total_seconds() > (expiry_hours * 3600):
            return False
            
        return True

    async def _check_auth(self, update: Update) -> bool:
        """Check if user is whitelisted or has a valid session."""
        user = update.effective_user
        if self.mcp.auth.is_whitelisted(user.id):
            return True
        
        session = self._get_session(user.id)
        if self._is_session_valid(session):
            return True
        
        await update.message.reply_text(
            "🔒 **Authentication Required**\n\n"
            "Please log in to use this command.\n"
            "Use `/login <password>`.",
            parse_mode='Markdown'
        )
        return False
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start - Welcome and start fresh session."""
        user = update.effective_user
        
        # Clear existing context and start fresh
        if self.agent:
            self.agent.clear_context(user.id)
        
        # Reset session but keep auth if valid
        existing_auth = False
        login_time = None
        if user.id in self.sessions:
            if self._is_session_valid(self.sessions[user.id]):
                existing_auth = True
                login_time = self.sessions[user.id].get('login_time')

        self.sessions[user.id] = {
            'started': datetime.now(),
            'message_count': 0,
            'last_activity': datetime.now(),
            'authenticated': existing_auth,
            'login_time': login_time
        }
        
        welcome_text = f"""<b>Welcome, {user.first_name}!</b>

I'm your <b>Remote PC Agent</b> powered by AI.

<code>Just talk naturally:</code>
  - "Check my disk space"
  - "Send me resume.pdf from Documents"
  - "Create a Python script that..."
  - "List my GitHub repositories"

<b>Commands:</b>
  <code>/models</code> - Select AI model
  <code>/new</code> - Start fresh conversation
  <code>/clear</code> - Clear context only
  <code>/session</code> - View session info
  <code>/send</code> - Send a file

<i>I remember our conversation context.</i>"""
        
        if not self.mcp.auth.is_whitelisted(user.id) and not existing_auth:
             welcome_text += "\n\n🔒 <b>Authentication Required</b>\nPlease use <code>/login password</code> to access."
        
        await update.message.reply_text(welcome_text, parse_mode='HTML')
    
    async def _handle_new_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /new - Start a completely fresh session."""
        user = update.effective_user
        
        # Clear context
        if self.agent:
            self.agent.clear_context(user.id)
        
        # Reset session but keep auth
        existing_auth = False
        login_time = None
        if user.id in self.sessions:
             if self._is_session_valid(self.sessions[user.id]):
                existing_auth = True
                login_time = self.sessions[user.id].get('login_time')

        self.sessions[user.id] = {
            'started': datetime.now(),
            'message_count': 0,
            'last_activity': datetime.now(),
            'authenticated': existing_auth,
            'login_time': login_time
        }
        
        await update.message.reply_text(
            "🆕 **New Session Started!**\n\n"
            "Previous conversation cleared.\n"
            "Let's start fresh - what can I help you with?",
            parse_mode='Markdown'
        )
    
    async def _handle_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear - Clear context but keep session stats."""
        user = update.effective_user
        
        if self.agent:
            self.agent.clear_context(user.id)
        
        await update.message.reply_text(
            "🧹 **Conversation Cleared!**\n\n"
            "I've forgotten our previous conversation.\n"
            "Session stats kept. Use `/new` for a complete reset.",
            parse_mode='Markdown'
        )
    
    async def _handle_session_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /session - Show session information."""
        user = update.effective_user
        session = self._get_session(user.id)
        
        # Get context info
        context_msgs = 0
        if self.agent and user.id in self.agent.contexts:
            context_msgs = len(self.agent.contexts[user.id].messages)
        
        duration = datetime.now() - session['started']
        hours, remainder = divmod(int(duration.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            duration_str = f"{hours}h {minutes}m"
        elif minutes > 0:
            duration_str = f"{minutes}m {seconds}s"
        else:
            duration_str = f"{seconds}s"
            
        is_auth = self._is_session_valid(session) or self.mcp.auth.is_whitelisted(user.id)
        auth_status = "✅ Authenticated" if is_auth else "🔒 Locked"
        if session.get('login_time'):
            expiry = self.mcp.config.get('security', {}).get('session_expiry_hours', 24)
            expires_at = session['login_time'].timestamp() + (expiry * 3600)
            remaining = expires_at - datetime.now().timestamp()
            if remaining > 0:
                 r_hours = int(remaining // 3600)
                 r_mins = int((remaining % 3600) // 60)
                 auth_status += f" (Expires in {r_hours}h {r_mins}m)"
            else:
                 auth_status += " (Expired)"
        
        status_text = f"""
📊 **Session Info**

👤 **User:** {user.first_name} (@{user.username or 'N/A'})
🆔 **ID:** `{user.id}`

📈 **This Session:**
• Started: {session['started'].strftime('%H:%M:%S')}
• Duration: {duration_str}
• Messages: {session['message_count']}
• Context Size: {context_msgs} messages

🔧 **Settings:**
• Mode: {'🤖 Agent' if self.agent_mode else '⚡ Raw'}
• OpenCode: {'✅ Active' if self.agent else '❌ Inactive'}
• Status: {auth_status}

💡 Use `/new` to start fresh or `/clear` to reset context.
        """
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
    
    async def _handle_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history - Show recent conversation."""
        user = update.effective_user
        
        if not self._check_auth(update): return

        if not self.agent or user.id not in self.agent.contexts:
            await update.message.reply_text(
                "📭 No conversation history yet.\n\nStart chatting to build context!",
                parse_mode='Markdown'
            )
            return
        
        user_context = self.agent.contexts[user.id]
        if not user_context.messages:
            await update.message.reply_text("📭 No messages in current context.")
            return
        
        history_parts = ["📜 **Recent Conversation:**\n"]
        
        for i, msg in enumerate(user_context.messages[-6:], 1):  # Last 6 messages
            role_emoji = "👤" if msg.role == "user" else "🤖"
            content = msg.content[:150] + "..." if len(msg.content) > 150 else msg.content
            content = content.replace('\n', ' ')  # Keep it compact
            history_parts.append(f"{role_emoji} {content}")
        
        history_parts.append(f"\n_Showing {min(6, len(user_context.messages))} of {len(user_context.messages)} messages_")
        
        await update.message.reply_text(
            "\n\n".join(history_parts),
            parse_mode='Markdown'
        )
    
    async def _handle_models(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /models - List available AI models with inline buttons."""
        user = update.effective_user
        
        if not self._check_auth(update): return

        if not self.agent:
            await update.message.reply_text("<b>Error:</b> Agent not available.", parse_mode='HTML')
            return
        
        models = self.agent.get_available_models()
        current_model = self.agent.get_user_model(user.id)
        
        # Create inline keyboard with model buttons (2 per row)
        keyboard = []
        row = []
        for i, (model_id, model_name) in enumerate(models):
            # Shorten name for button
            short_name = model_name.replace(" (Antigravity)", "").replace(" Preview", "")
            marker = "• " if model_id == current_model else ""
            row.append(InlineKeyboardButton(f"{marker}{short_name}", callback_data=f"model:{model_id}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Find current model name
        current_name = next((m[1] for m in models if m[0] == current_model), current_model)
        
        await update.message.reply_text(
            f"<b>Select AI Model</b>\n\n"
            f"<code>Current:</code> <b>{current_name}</b>\n\n"
            f"<i>Tap a button to switch models</i>",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def _handle_model_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle model selection button callback."""
        query = update.callback_query
        user = query.from_user
        
        if not self.mcp.auth.is_whitelisted(user.id):
             session = self._get_session(user.id)
             if not self._is_session_valid(session):
                  await query.answer("Auth required", show_alert=True)
                  return

        await query.answer()
        
        model_id = query.data.replace("model:", "")
        
        if not self.agent:
            await query.edit_message_text("<b>Error:</b> Agent not available.", parse_mode='HTML')
            return
        
        models = self.agent.get_available_models()
        model_name = next((m[1] for m in models if m[0] == model_id), None)
        
        if model_name and self.agent.set_user_model(user.id, model_id):
            # Rebuild keyboard with updated current marker
            keyboard = []
            row = []
            for i, (mid, mname) in enumerate(models):
                short_name = mname.replace(" (Antigravity)", "").replace(" Preview", "")
                marker = "• " if mid == model_id else ""
                row.append(InlineKeyboardButton(f"{marker}{short_name}", callback_data=f"model:{mid}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"<b>Select AI Model</b>\n\n"
                f"<code>Current:</code> <b>{model_name}</b>\n\n"
                f"<i>Model changed successfully</i>",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(f"<b>Error:</b> Invalid model.", parse_mode='HTML')
    
    async def _handle_set_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /model <id> - Set active AI model."""
        user = update.effective_user
        
        if not self._check_auth(update): return

        if not self.agent:
            await update.message.reply_text("⚠️ Agent not available.")
            return
        
        if not context.args:
            # Show current model
            current = self.agent.get_user_model(user.id)
            await update.message.reply_text(
                f"📌 **Current Model:** `{current}`\n\n"
                "Use `/models` to see available options.\n"
                "Use `/model <number>` or `/model <model_id>` to switch.",
                parse_mode='Markdown'
            )
            return
        
        selection = ' '.join(context.args).strip()
        models = self.agent.get_available_models()
        
        # Check if selection is a number
        try:
            idx = int(selection) - 1
            if 0 <= idx < len(models):
                model_id = models[idx][0]
                model_name = models[idx][1]
            else:
                await update.message.reply_text(
                    f"❌ Invalid number. Choose 1-{len(models)}.\n\nUse `/models` to see options.",
                    parse_mode='Markdown'
                )
                return
        except ValueError:
            # Assume it's a model_id
            model_id = selection
            model_name = next((m[1] for m in models if m[0] == model_id), None)
            if not model_name:
                await update.message.reply_text(
                    f"❌ Unknown model: `{model_id}`\n\nUse `/models` to see available options.",
                    parse_mode='Markdown'
                )
                return
        
        # Set the model
        if self.agent.set_user_model(user.id, model_id):
            await update.message.reply_text(
                f"✅ **Model Changed!**\n\n"
                f"🤖 Now using: **{model_name}**\n"
                f"`{model_id}`\n\n"
                f"All new messages will use this model.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ Failed to set model: `{model_id}`", parse_mode='Markdown')
    
    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        user = update.effective_user
        if not self.mcp.auth.is_whitelisted(user.id):
            session = self._get_session(user.id)
            if not self._is_session_valid(session):
                  await update.message.reply_text(
                       "🔒 **Authentication Required**\n\n"
                       "Please log in to see available commands.\n"
                       "Use `/login <password>`.",
                       parse_mode='Markdown'
                  )
                  return

        help_text = """
🤖 **Remote PC Agent Help**

**Just type naturally!** I understand:
• "Show files in my Documents"
• "Send me all PDFs from Desktop"
• "Create a backup script"
• "What's using my memory?"

**Session Commands:**
• `/start` - Welcome + fresh start
• `/new` - New conversation
• `/clear` - Clear context
• `/session` - Session info
• `/history` - View recent messages

**File Commands:**
• `/send <path>` - Send specific file
• Or just ask: "Send me report.pdf"

**Auth Commands:**
• `/login <password>` - Log in
• `/logout` - Log out

**Tips:**
• I remember context - refer to previous messages!
• Say "send that file" after discussing one
• Use `/new` when switching topics
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def _handle_send_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /send - Direct file send."""
        if not self._check_auth(update): return

        filepath = ' '.join(context.args) if context.args else ''
        if not filepath:
            await update.message.reply_text(
                "📁 **Usage:** `/send <filepath>`\n\n"
                "Example: `/send C:\\Users\\arya2\\Documents\\report.pdf`",
                parse_mode='Markdown'
            )
            return
        
        await self._send_file_to_user(update, filepath)
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all non-command messages."""
        text = update.message.text.strip()
        user = update.effective_user
        
        # Auth check
        if not await self._check_auth(update):
            # If they just sent a valid password as a message, try to log them in
            if self.mcp.auth.verify_password(text):
                session = self._get_session(user.id)
                session['authenticated'] = True
                session['login_time'] = datetime.now()
                hours = self.mcp.config.get('security', {}).get('session_expiry_hours', 24)
                await update.message.reply_text(f"✅ Login successful! Session valid for {hours} hours.")
                self.logger.info(f"User {user.id} logged in via text message")
                # Don't process the password as a command/prompt
                return
            return
        
        # Update session
        self._update_session(user.id)
        
        # Raw shortcuts
        if text.startswith('$') or text.startswith('>>>'):
            await self._execute_raw_and_reply(update, text)
            return
            
        # Check specific mode
        session = self._get_session(user.id)
        if session['mode'] != self.STATE_NORMAL:
            await self._handle_code_flow(update, text, session)
            return
        
        # Process with OpenCode
        if self.agent:
            await self._process_with_agent(update, text)
        else:
            await update.message.reply_text("⚠️ Agent not available.")

    async def _handle_code_flow(self, update: Update, text: str, session: dict):
        """Handle messages when in a specific state."""
        mode = session['mode']
        
        if mode == self.STATE_WAITING_DIR:
            # Validate directory
            path = text.strip().strip('"\'')
            
            try:
                # Try to create if it doesn't exist
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                    await update.message.reply_text(f"✨ Created new directory: `{path}`", parse_mode='Markdown')
                
                if os.path.isdir(path):
                    session['project_dir'] = path
                    session['mode'] = self.STATE_WAITING_GOAL
                    await update.message.reply_text(
                        f"📂 **Directory Set:** `{path}`\n\n"
                        "Now, please describe the **task or goal** for this session.\n"
                        "I will create a plan and we'll start.",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        f"❌ Invalid directory: `{path}`\n"
                        "Please enter a valid absolute path."
                    )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Could not create/access directory: `{path}`\n"
                    f"Error: {str(e)}"
                )
                
        elif mode == self.STATE_WAITING_GOAL:
            session['project_goal'] = text
            session['mode'] = self.STATE_CODING
            
            # Trigger initial plan
            goal = session['project_goal']
            directory = session['project_dir']
            
            await update.message.reply_text(
                f"🎯 **Goal Set:** {goal}\n\n"
                "🧠 **Thinking...** generating initial plan..."
            )
            
            initial_prompt = (
                f"I am starting a new task.\n"
                f"Goal: {goal}\n"
                f"Please create a step-by-step implementation plan."
            )
            
            # Pass to agent with special context
            await self._process_with_agent(
                update, 
                initial_prompt, 
                working_dir=directory,
                system_context=f"Project: {goal}\nLocation: {directory}"
            )
            
        elif mode == self.STATE_CODING:
            # Normal conversation but with locked context
            goal = session['project_goal']
            directory = session['project_dir']
            
            await self._process_with_agent(
                update, 
                text, 
                working_dir=directory,
                system_context=f"Project: {goal}\nLocation: {directory}"
            )
    
    async def _process_with_agent(
        self, 
        update: Update, 
        text: str, 
        working_dir: str = None, 
        system_context: str = None
    ):
        """Process message through OpenCode agent."""
        user = update.effective_user
        
        await update.message.chat.send_action('typing')
        status_msg = await update.message.reply_text("🤔 Thinking...")
        
        try:
            is_file_request = self._is_file_send_request(text)
            
            if is_file_request:
                enhanced_text = self._enhance_file_request(text)
            else:
                enhanced_text = text
            
            result = await self.agent.process(
                enhanced_text,
                user.id,
                username=user.username or str(user.id),
                working_dir=working_dir,
                system_context=system_context
            )
            
            await status_msg.delete()
            
            if is_file_request:
                files_to_send = self._extract_file_paths(result, text)
                
                if files_to_send:
                    await self._send_response(update, f"📁 Found {len(files_to_send)} file(s)")
                    for filepath in files_to_send[:10]:
                        await self._send_file_to_user(update, filepath)
                else:
                    await self._send_response(update, result)
            else:
                await self._send_response(update, result)
            
        except Exception as e:
            self.logger.error(f"Agent error: {e}", exc_info=True)
            await status_msg.edit_text(f"⚠️ Error: {str(e)}")
    
    def _is_file_send_request(self, text: str) -> bool:
        """Detect file send requests."""
        text_lower = text.lower()
        send_keywords = ['send', 'give', 'transfer', 'get me', 'fetch', 'download']
        file_indicators = ['file', 'image', 'photo', 'jpg', 'png', 'pdf', 'document', 
                          'picture', 'screenshot', 'from desktop', 'from documents']
        
        has_send = any(kw in text_lower for kw in send_keywords)
        has_file = any(fi in text_lower for fi in file_indicators)
        
        return has_send and has_file
    
    def _enhance_file_request(self, text: str) -> str:
        """Enhance file request prompt."""
        return f"""The user wants files sent to them via Telegram. 
{text}

IMPORTANT: List the FULL ABSOLUTE PATHS of matching files, one per line.
Start each path with the drive letter (e.g., C:\\Users\\...).
If no files found, explain why."""
    
    def _extract_file_paths(self, response: str, original_request: str) -> List[str]:
        """Extract file paths from response."""
        files = []
        
        patterns = [
            r'[A-Za-z]:\\[^\r\n\t"<>|*?]+\.[a-zA-Z0-9]+',
            r'[A-Za-z]:/[^\r\n\t"<>|*?]+\.[a-zA-Z0-9]+',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                filepath = match.strip().rstrip('.,;:')
                if os.path.exists(filepath) and os.path.isfile(filepath):
                    if filepath not in files:
                        files.append(filepath)
        
        return files
    
    async def _send_file_to_user(self, update: Update, filepath: str):
        """Send a file to user."""
        filepath = filepath.strip().strip('"\'')
        
        if not os.path.exists(filepath):
            await update.message.reply_text(f"❌ Not found: `{filepath}`", parse_mode='Markdown')
            return
        
        if not os.path.isfile(filepath):
            await update.message.reply_text(f"❌ Not a file: `{filepath}`", parse_mode='Markdown')
            return
        
        file_size = os.path.getsize(filepath)
        if file_size > self.MAX_FILE_SIZE:
            await update.message.reply_text(f"❌ Too large: {file_size/(1024*1024):.1f}MB (max 50MB)")
            return
        
        ext = Path(filepath).suffix.lower()
        filename = Path(filepath).name
        
        try:
            await update.message.chat.send_action('upload_document')
            
            with open(filepath, 'rb') as f:
                if ext in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}:
                    await update.message.reply_photo(photo=InputFile(f, filename=filename), caption=f"📷 {filename}")
                elif ext in {'.mp4', '.avi', '.mov', '.mkv'}:
                    await update.message.reply_video(video=InputFile(f, filename=filename), caption=f"🎬 {filename}")
                elif ext in {'.mp3', '.wav', '.ogg'}:
                    await update.message.reply_audio(audio=InputFile(f, filename=filename), caption=f"🎵 {filename}")
                else:
                    await update.message.reply_document(document=InputFile(f, filename=filename), caption=f"📄 {filename}")
            
            self.logger.info(f"Sent: {filepath}")
            
        except Exception as e:
            self.logger.error(f"Send failed {filepath}: {e}")
            await update.message.reply_text(f"❌ Failed: {str(e)}")
    
    async def _execute_raw_and_reply(self, update: Update, command: str):
        """Execute raw command."""
        user = update.effective_user
        await update.message.chat.send_action('typing')
        
        result = await self.mcp.execute_command(command, user.id, user.username or str(user.id))
        
        self.audit.log_command(
            user_id=user.id,
            username=user.username or str(user.id),
            command=command,
            tool="telegram",
            result=result[:100],
            success="❌" not in result[:50]
        )
        
        await self._send_response(update, result)
    
    async def _send_response(self, update: Update, text: str):
        """Send response, detecting questions and splitting if needed."""
        max_len = 4000
        text = text or "✅ Done"
        
        # Detect if agent is asking a question
        is_question = self._is_asking_question(text)
        
        if is_question:
            # Add visual indicator that user should respond
            text = text.rstrip() + "\n\n💬 _Reply to answer..._"
        
        if len(text) <= max_len:
            try:
                await update.message.reply_text(text, parse_mode='Markdown')
            except:
                await update.message.reply_text(text)
        else:
            chunks = [text[i:i+max_len] for i in range(0, len(text), max_len)]
            for i, chunk in enumerate(chunks):
                prefix = f"📄 {i+1}/{len(chunks)}\n\n" if len(chunks) > 1 else ""
                try:
                    await update.message.reply_text(prefix + chunk, parse_mode='Markdown')
                except:
                    await update.message.reply_text(prefix + chunk)
    
    def _is_asking_question(self, text: str) -> bool:
        """Detect if the agent response contains a question for the user."""
        # Look for question patterns at the end of the message
        text_lower = text.lower().strip()
        
        # Question indicators
        question_patterns = [
            r'\?[\s]*$',  # Ends with question mark
            r'what (?:should|would|do you)',
            r'(?:which|what) (?:name|option|one)',
            r'would you like',
            r'do you want',
            r'can you (?:provide|specify|tell)',
            r'please (?:provide|specify|tell|choose)',
            r'(?:let me know|confirm)',
        ]
        
        for pattern in question_patterns:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    async def _check_auth(self, update: Update) -> bool:
        """
        Check if user is allowed to proceed.
        Returns: True if authorized, False (and replies) if not.
        """
        user = update.effective_user
        
        # 1. Check strict whitelist
        if self.mcp.auth.is_whitelisted(user.id):
            return True
            
        # 2. Check session authentication
        session = self._get_session(user.id)
        if self._is_session_valid(session):
            return True
            
        # 3. Deny access
        if session.get('login_time'):
            # Expired
            await update.message.reply_text("⌛ **Session Expired**\n\nPlease log in again: `/login <password>`", parse_mode='Markdown')
        else:
            # Never logged in
            await update.message.reply_text("🔒 **Authentication Required**\n\nPlease log in: `/login <password>`", parse_mode='Markdown')
            
        return False

    async def setup_commands(self):
        """Set up bot command menu."""
        commands = [
            BotCommand("start", "🚀 Start fresh"),
            BotCommand("code", "💻 Coding Mode"),
            BotCommand("new", "🆕 New conversation"),
            BotCommand("clear", "🧹 Clear context"),
            BotCommand("models", "🤖 List AI models"),
            BotCommand("model", "🔄 Change model"),
            BotCommand("session", "📊 Session info"),
            BotCommand("history", "📜 View history"),
            BotCommand("login", "🔓 Log in"),
            BotCommand("logout", "🔒 Log out"),
            BotCommand("help", "❓ Help"),
            BotCommand("send", "📁 Send file"),
        ]
        await self.app.bot.set_my_commands(commands)
    
    async def start(self):
        """Start the Telegram bot."""
        self.logger.info("Starting Telegram bot...")
        await self.app.initialize()
        await self.setup_commands()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        self.logger.info("Telegram bot started!")
    
    async def stop(self):
        """Stop the Telegram bot."""
        self.logger.info("Stopping Telegram bot...")
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
