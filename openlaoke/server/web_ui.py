"""Web UI module - Full-featured web interface for LAN access."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from openlaoke.core.config_wizard import get_proxy_url
from openlaoke.core.multi_provider_api import MultiProviderClient
from openlaoke.core.sessions import SessionManager
from openlaoke.core.state import AppState, create_app_state
from openlaoke.core.system_prompt import build_system_prompt
from openlaoke.core.tool import ToolContext, ToolRegistry
from openlaoke.tools.register import register_all_tools
from openlaoke.types.core_types import (
    AssistantMessage,
    CostInfo,
    MessageRole,
    TokenUsage,
    UserMessage,
)
from openlaoke.utils.config import AppConfig, load_config, save_config

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenLaoKe Web UI</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --accent: #58a6ff;
            --accent-secondary: #3fb950;
            --error: #f85149;
            --border: #30363d;
        }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: var(--bg-primary); color: var(--text-primary); height: 100vh; display: flex; flex-direction: column; }
        header { background: var(--bg-secondary); border-bottom: 1px solid var(--border); padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; }
        header h1 { font-size: 18px; font-weight: 600; color: var(--accent); }
        .header-info { display: flex; gap: 20px; font-size: 13px; color: var(--text-secondary); }
        .header-info span { display: flex; align-items: center; gap: 6px; }
        .main-container { flex: 1; display: flex; overflow: hidden; }
        .sidebar { width: 260px; background: var(--bg-secondary); border-right: 1px solid var(--border); display: flex; flex-direction: column; }
        .sidebar-header { padding: 12px 16px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .sidebar-header h2 { font-size: 14px; font-weight: 600; }
        .new-chat-btn { background: var(--accent); color: #fff; border: none; padding: 6px 12px; border-radius: 6px; font-size: 13px; cursor: pointer; }
        .new-chat-btn:hover { opacity: 0.9; }
        .sessions-list { flex: 1; overflow-y: auto; padding: 8px; }
        .session-item { padding: 10px 12px; border-radius: 6px; cursor: pointer; margin-bottom: 4px; font-size: 13px; color: var(--text-secondary); display: flex; justify-content: space-between; align-items: center; }
        .session-item:hover { background: var(--bg-tertiary); }
        .session-item.active { background: var(--bg-tertiary); color: var(--text-primary); }
        .session-item .session-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
        .session-item .session-time { font-size: 11px; color: var(--text-muted); }
        .chat-area { flex: 1; display: flex; flex-direction: column; }
        .messages-container { flex: 1; overflow-y: auto; padding: 20px; }
        .message { margin-bottom: 20px; max-width: 85%; }
        .message.user { margin-left: auto; }
        .message.assistant { margin-right: auto; }
        .message-header { font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
        .message.user .message-header { text-align: right; }
        .message-content { padding: 12px 16px; border-radius: 12px; line-height: 1.6; font-size: 14px; }
        .message.user .message-content { background: var(--accent); color: #fff; border-bottom-right-radius: 4px; }
        .message.assistant .message-content { background: var(--bg-tertiary); border-bottom-left-radius: 4px; }
        .message.assistant .message-content pre { background: var(--bg-primary); padding: 12px; border-radius: 6px; overflow-x: auto; margin: 8px 0; }
        .message.assistant .message-content code { background: var(--bg-primary); padding: 2px 6px; border-radius: 4px; font-family: 'SF Mono', Monaco, monospace; font-size: 13px; }
        .message.assistant .message-content pre code { padding: 0; background: none; }
        .tool-call { background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; margin: 8px 0; font-size: 13px; }
        .tool-call-name { color: var(--accent); font-weight: 500; }
        .tool-call-args { color: var(--text-secondary); margin-top: 4px; font-family: 'SF Mono', Monaco, monospace; font-size: 12px; white-space: pre-wrap; }
        .tool-result { background: var(--bg-primary); border-radius: 6px; padding: 8px 12px; margin-top: 8px; font-size: 12px; color: var(--text-secondary); max-height: 200px; overflow-y: auto; }
        .tool-result.error { border-left: 3px solid var(--error); }
        .input-area { background: var(--bg-secondary); border-top: 1px solid var(--border); padding: 16px 20px; }
        .input-container { display: flex; gap: 12px; align-items: flex-end; }
        .input-wrapper { flex: 1; position: relative; }
        textarea { width: 100%; background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: 12px; padding: 12px 16px; color: var(--text-primary); font-size: 14px; font-family: inherit; resize: none; min-height: 52px; max-height: 200px; outline: none; }
        textarea:focus { border-color: var(--accent); }
        textarea::placeholder { color: var(--text-muted); }
        .send-btn { background: var(--accent); color: #fff; border: none; padding: 14px 24px; border-radius: 12px; font-size: 14px; font-weight: 500; cursor: pointer; transition: opacity 0.2s; }
        .send-btn:hover { opacity: 0.9; }
        .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .status-bar { background: var(--bg-tertiary); padding: 8px 20px; font-size: 12px; color: var(--text-muted); display: flex; gap: 20px; }
        .status-item { display: flex; align-items: center; gap: 6px; }
        .status-item .indicator { width: 8px; height: 8px; border-radius: 50%; background: var(--accent-secondary); }
        .status-item.error .indicator { background: var(--error); }
        .typing-indicator { display: none; padding: 12px 16px; color: var(--text-secondary); font-size: 14px; }
        .typing-indicator.active { display: block; }
        .typing-dots { display: inline-block; }
        .typing-dots::after { content: ''; animation: dots 1.5s infinite; }
        @keyframes dots { 0%,20% { content: ''; } 40% { content: '.'; } 60% { content: '..'; } 80%,100% { content: '...'; } }
        .tool-panel { position: fixed; right: 20px; top: 80px; width: 320px; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 12px; padding: 16px; max-height: calc(100vh - 100px); overflow-y: auto; display: none; }
        .tool-panel.visible { display: block; }
        .tool-panel h3 { font-size: 14px; margin-bottom: 12px; color: var(--text-secondary); }
        .tool-list { display: flex; flex-direction: column; gap: 8px; }
        .tool-item { padding: 8px 12px; background: var(--bg-tertiary); border-radius: 6px; font-size: 13px; color: var(--text-secondary); cursor: pointer; }
        .tool-item:hover { background: var(--bg-primary); color: var(--text-primary); }
        .empty-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--text-muted); }
        .empty-state h2 { font-size: 24px; margin-bottom: 8px; color: var(--text-secondary); }
        .empty-state p { font-size: 14px; }
        .config-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.7); display: none; align-items: center; justify-content: center; z-index: 100; }
        .config-modal.visible { display: flex; }
        .config-content { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 12px; padding: 24px; width: 480px; max-width: 90%; }
        .config-content h2 { font-size: 18px; margin-bottom: 16px; }
        .config-row { margin-bottom: 16px; }
        .config-row label { display: block; font-size: 13px; color: var(--text-secondary); margin-bottom: 6px; }
        .config-row select, .config-row input { width: 100%; padding: 10px 12px; background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: 6px; color: var(--text-primary); font-size: 14px; }
        .config-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; }
        .config-actions button { padding: 10px 20px; border-radius: 6px; font-size: 14px; cursor: pointer; border: none; }
        .config-actions .cancel { background: var(--bg-tertiary); color: var(--text-primary); }
        .config-actions .save { background: var(--accent); color: #fff; }
    </style>
</head>
<body>
    <header>
        <h1>🤖 OpenLaoKe</h1>
        <div class="header-info">
            <span>📡 <span id="model-name">-</span></span>
            <span>💰 <span id="cost-display">$0.00</span></span>
            <span>🔢 <span id="token-display">0</span> tokens</span>
            <button class="new-chat-btn" onclick="newSession()">+ New Chat</button>
        </div>
    </header>
    <div class="main-container">
        <div class="sidebar">
            <div class="sidebar-header">
                <h2>History</h2>
            </div>
            <div class="sessions-list" id="sessions-list"></div>
        </div>
        <div class="chat-area">
            <div class="messages-container" id="messages-container">
                <div class="empty-state" id="empty-state">
                    <h2>Welcome to OpenLaoKe</h2>
                    <p>Start a conversation by typing below</p>
                </div>
            </div>
            <div class="typing-indicator" id="typing-indicator">
                <span class="typing-dots">Thinking</span>
            </div>
            <div class="input-area">
                <div class="input-container">
                    <div class="input-wrapper">
                        <textarea id="message-input" placeholder="Type your message... (Shift+Enter for new line, Enter to send)" rows="1"></textarea>
                    </div>
                    <button class="send-btn" id="send-btn" onclick="sendMessage()">Send</button>
                </div>
            </div>
            <div class="status-bar">
                <div class="status-item"><span class="indicator"></span><span id="connection-status">Connected</span></div>
                <div class="status-item">Working dir: <span id="cwd-display">-</span></div>
                <div class="status-item">Session: <span id="session-id-short">-</span></div>
            </div>
        </div>
    </div>
    <script>
        let ws = null;
        let currentSessionId = null;
        let sessions = [];
        const messagesContainer = document.getElementById('messages-container');
        const messageInput = document.getElementById('message-input');
        const sendBtn = document.getElementById('send-btn');
        const typingIndicator = document.getElementById('typing-indicator');

        function connect() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${location.host}/ws`);
            ws.onopen = () => { document.getElementById('connection-status').textContent = 'Connected'; };
            ws.onclose = () => { document.getElementById('connection-status').textContent = 'Disconnected'; setTimeout(connect, 3000); };
            ws.onerror = () => { document.getElementById('connection-status').textContent = 'Error'; };
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'connected') { loadSessions(); loadConfig(); }
                else if (data.type === 'chat_started') { currentSessionId = data.session_id; }
                else if (data.type === 'chat_chunk') { appendAssistantChunk(data.content); }
                else if (data.type === 'chat_complete') { finishAssistantMessage(); updateStats(); loadSessions(); }
                else if (data.type === 'message_complete') { updateTokenStats(data.usage, data.cost); }
                else if (data.type === 'pong') {}
            };
        }

        async function loadConfig() {
            const res = await fetch('/api/config');
            const config = await res.json();
            document.getElementById('model-name').textContent = `${config.active_provider}/${config.active_model}`;
            document.getElementById('cwd-display').textContent = '/';
        }

        async function loadSessions() {
            const res = await fetch('/api/session?limit=50');
            sessions = await res.json();
            renderSessions();
        }

        function renderSessions() {
            const list = document.getElementById('sessions-list');
            list.innerHTML = sessions.map(s => `
                <div class="session-item ${s.session_id === currentSessionId ? 'active' : ''}" onclick="loadSession('${s.session_id}')">
                    <span class="session-name">${s.message_count > 0 ? `Chat (${s.message_count} msgs)` : 'Empty session'}</span>
                    <span class="session-time">${s.created_at ? new Date(s.created_at * 1000).toLocaleDateString() : ''}</span>
                </div>
            `).join('');
        }

        async function loadSession(sessionId) {
            currentSessionId = sessionId;
            renderSessions();
            const res = await fetch(`/api/session/${sessionId}`);
            const session = await res.json();
            document.getElementById('session-id-short').textContent = sessionId.substring(0, 8);
        }

        function newSession() {
            fetch('/api/session', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({}) })
                .then(r => r.json())
                .then(session => { currentSessionId = session.session_id; messagesContainer.innerHTML = ''; renderSessions(); });
        }

        let currentAssistantDiv = null;
        let assistantContent = '';

        function appendAssistantChunk(text) {
            document.getElementById('empty-state').style.display = 'none';
            typingIndicator.classList.remove('active');
            if (!currentAssistantDiv) {
                currentAssistantDiv = document.createElement('div');
                currentAssistantDiv.className = 'message assistant';
                currentAssistantDiv.innerHTML = `<div class="message-header">OpenLaoKe</div><div class="message-content"></div>`;
                messagesContainer.appendChild(currentAssistantDiv);
                assistantContent = '';
            }
            assistantContent += text;
            currentAssistantDiv.querySelector('.message-content').innerHTML = formatMarkdown(assistantContent);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        function finishAssistantMessage() {
            if (currentAssistantDiv) {
                currentAssistantDiv.querySelector('.message-content').innerHTML = formatMarkdown(assistantContent);
                currentAssistantDiv = null;
                assistantContent = '';
            }
        }

        function formatMarkdown(text) {
            return text.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
                       .replace(/`([^`]+)`/g, '<code>$1</code>')
                       .replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>')
                       .replace(/\\n/g, '<br>');
        }

        function updateStats() {
            let totalCost = 0;
            let totalTokens = 0;
            document.querySelectorAll('.message').forEach(m => {
                const cost = parseFloat(m.dataset.cost || 0);
                const tokens = parseInt(m.dataset.tokens || 0);
                totalCost += cost;
                totalTokens += tokens;
            });
            document.getElementById('cost-display').textContent = '$' + totalCost.toFixed(4);
            document.getElementById('token-display').textContent = totalTokens;
        }

        function updateTokenStats(usage, cost) {
            const current = parseFloat(document.getElementById('cost-display').textContent.replace('$', '')) || 0;
            document.getElementById('cost-display').textContent = '$' + (current + cost).toFixed(4);
            const tokens = parseInt(document.getElementById('token-display').textContent) || 0;
            document.getElementById('token-display').textContent = tokens + (usage?.input_tokens || 0) + (usage?.output_tokens || 0);
        }

        function addUserMessage(content) {
            document.getElementById('empty-state').style.display = 'none';
            const div = document.createElement('div');
            div.className = 'message user';
            div.innerHTML = `<div class="message-header">You</div><div class="message-content">${formatMarkdown(content)}</div>`;
            messagesContainer.appendChild(div);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        async function sendMessage() {
            const content = messageInput.value.trim();
            if (!content || !ws || ws.readyState !== WebSocket.OPEN) return;
            addUserMessage(content);
            messageInput.value = '';
            typingIndicator.classList.add('active');
            ws.send(JSON.stringify({ type: 'chat', session_id: currentSessionId, content }));
        }

        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        messageInput.addEventListener('input', () => {
            messageInput.style.height = 'auto';
            messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
        });

        connect();
    </script>
</body>
</html>"""


class ChatRequest(BaseModel):
    content: str = ""
    session_id: str | None = None
    stream: bool = True


class ChatResponse(BaseModel):
    session_id: str
    content: str = ""
    tool_uses: list[dict[str, Any]] = []
    usage: dict[str, int] = {}
    cost: float = 0.0


class ToolRequest(BaseModel):
    name: str
    input: dict[str, Any] = {}
    session_id: str | None = None


class ToolResponse(BaseModel):
    tool_use_id: str
    content: str | list[dict[str, Any]]
    is_error: bool = False


class SessionCreateRequest(BaseModel):
    cwd: str | None = None
    model: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    cwd: str
    message_count: int
    task_count: int
    model: str
    created_at: float


class ConfigUpdateRequest(BaseModel):
    max_tokens: int | None = None
    temperature: float | None = None
    thinking_budget: int | None = None
    permission_mode: str | None = None
    theme: str | None = None


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    enabled: bool = True


class ToolInfo(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    is_read_only: bool = False
    is_destructive: bool = False


@dataclass
class ActiveSession:
    app_state: AppState
    registry: ToolRegistry
    api: MultiProviderClient
    config: AppConfig
    created_at: float = field(default_factory=time.time)


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            for connection in self.active_connections:
                with contextlib.suppress(Exception):
                    await connection.send_json(message)

    async def send_personal(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        with contextlib.suppress(Exception):
            await websocket.send_json(message)


class WebUI:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        cors_origins: list[str] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.cors_origins = cors_origins or ["*"]
        self.app = FastAPI(
            title="OpenLaoKe Web UI",
            description="Full-featured web interface for OpenLaoKe",
            version="1.0.0",
        )
        self.manager = ConnectionManager()
        self.sessions: dict[str, ActiveSession] = {}
        self.session_manager = SessionManager()
        self._setup_middleware()
        self._setup_routes()

    def _setup_middleware(self) -> None:
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self) -> None:
        app = self.app

        @app.get("/")
        async def get_index() -> HTMLResponse:
            return HTMLResponse(content=HTML_PAGE, status_code=200)

        @app.get("/health")
        async def health_check() -> dict[str, str]:
            return {"status": "ok", "timestamp": str(time.time())}

        @app.post("/api/chat")
        async def chat(request: ChatRequest) -> StreamingResponse | ChatResponse:
            session = await self._get_or_create_session(request.session_id)
            session_id = session.app_state.session_id

            user_msg = UserMessage(role=MessageRole.USER, content=request.content)
            session.app_state.add_message(user_msg)

            if request.stream:
                return StreamingResponse(
                    self._stream_chat(session, request.content),
                    media_type="text/event-stream",
                )

            response, usage, cost = await self._send_message(session, request.content)
            return ChatResponse(
                session_id=session_id,
                content=response.content,
                tool_uses=[tu.to_dict() for tu in response.tool_uses],
                usage={
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                },
                cost=cost.total_cost,
            )

        @app.post("/api/tool")
        async def execute_tool(request: ToolRequest) -> ToolResponse:
            session = await self._get_or_create_session(request.session_id)
            tool = session.registry.get(request.name)
            if not tool:
                raise HTTPException(status_code=404, detail=f"Tool not found: {request.name}")

            validation = tool.validate_input(request.input)
            if not validation.result:
                raise HTTPException(status_code=400, detail=validation.message)

            tool_use_id = f"tool_{uuid.uuid4().hex[:8]}"
            ctx = ToolContext(app_state=session.app_state, tool_use_id=tool_use_id)

            result = await tool.call(ctx, **request.input)
            return ToolResponse(
                tool_use_id=tool_use_id,
                content=result.content if isinstance(result.content, str) else result.content,
                is_error=result.is_error,
            )

        @app.get("/api/session")
        async def list_sessions(
            limit: int = Query(default=50, ge=1, le=100),
        ) -> list[SessionResponse]:
            sessions = self.session_manager.list_sessions()[:limit]
            return [
                SessionResponse(
                    session_id=s.session_id,
                    cwd=s.cwd,
                    message_count=s.message_count,
                    task_count=s.task_count,
                    model=s.model,
                    created_at=s.created_at,
                )
                for s in sessions
            ]

        @app.post("/api/session")
        async def create_session(request: SessionCreateRequest) -> SessionResponse:
            config = load_config()
            cwd = request.cwd or os.getcwd()
            model = request.model or config.get_active_model()

            persist_dir = os.path.expanduser("~/.openlaoke/sessions")
            os.makedirs(persist_dir, exist_ok=True)
            persist_path = os.path.join(persist_dir, f"session_{int(time.time())}.json")

            app_state = create_app_state(cwd=cwd, model=model, persist_path=persist_path)
            app_state.session_config.model = model
            app_state.multi_provider_config = config.providers
            app_state.app_config = config

            registry = ToolRegistry()
            register_all_tools(registry)

            proxy_url = get_proxy_url(config)
            api = MultiProviderClient(config.providers, proxy=proxy_url)

            session_id = app_state.session_id
            self.sessions[session_id] = ActiveSession(
                app_state=app_state,
                registry=registry,
                api=api,
                config=config,
            )

            self.session_manager.save_session(app_state)

            return SessionResponse(
                session_id=session_id,
                cwd=cwd,
                message_count=0,
                task_count=0,
                model=model,
                created_at=time.time(),
            )

        @app.get("/api/session/{session_id}")
        async def get_session(session_id: str) -> SessionResponse:
            if session_id in self.sessions:
                s = self.sessions[session_id]
                return SessionResponse(
                    session_id=session_id,
                    cwd=s.app_state.cwd,
                    message_count=len(s.app_state.messages),
                    task_count=len(s.app_state.tasks),
                    model=s.app_state.session_config.model,
                    created_at=s.created_at,
                )

            app_state = self.session_manager.load_session(session_id)
            if not app_state:
                raise HTTPException(status_code=404, detail="Session not found")

            return SessionResponse(
                session_id=session_id,
                cwd=app_state.cwd,
                message_count=len(app_state.messages),
                task_count=len(app_state.tasks),
                model=app_state.session_config.model,
                created_at=0,
            )

        @app.delete("/api/session/{session_id}")
        async def delete_session(session_id: str) -> dict[str, bool]:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                await session.api.close()
                del self.sessions[session_id]

            deleted = self.session_manager.delete_session(session_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Session not found")

            return {"deleted": True}

        @app.get("/api/config")
        async def get_config() -> dict[str, Any]:
            config = load_config()
            return {
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "thinking_budget": config.thinking_budget,
                "permission_mode": config.permission_mode,
                "theme": config.theme,
                "show_token_budget": config.show_token_budget,
                "show_cost": config.show_cost,
                "enable_mcp": config.enable_mcp,
                "proxy_mode": config.proxy_mode,
                "proxy_url": config.proxy_url,
                "active_provider": config.providers.active_provider,
                "active_model": config.providers.active_model,
            }

        @app.put("/api/config")
        async def update_config(request: ConfigUpdateRequest) -> dict[str, Any]:
            config = load_config()

            if request.max_tokens is not None:
                config.max_tokens = request.max_tokens
            if request.temperature is not None:
                config.temperature = request.temperature
            if request.thinking_budget is not None:
                config.thinking_budget = request.thinking_budget
            if request.permission_mode is not None:
                config.permission_mode = request.permission_mode
            if request.theme is not None:
                config.theme = request.theme

            save_config(config)
            return {"updated": True}

        @app.get("/api/models")
        async def list_models() -> list[ModelInfo]:
            config = load_config()
            models = []
            for provider_name, provider in config.providers.providers.items():
                if provider.enabled:
                    models.append(
                        ModelInfo(
                            id=provider.default_model,
                            name=provider.default_model,
                            provider=provider_name,
                            enabled=True,
                        )
                    )
            return models

        @app.get("/api/tools")
        async def list_tools() -> list[ToolInfo]:
            registry = ToolRegistry()
            register_all_tools(registry)
            tools = registry.get_all()
            return [
                ToolInfo(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.get_input_schema(),
                    is_read_only=tool.is_read_only,
                    is_destructive=tool.is_destructive,
                )
                for tool in tools
            ]

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket) -> None:
            await self.manager.connect(websocket)
            try:
                await self.manager.send_personal(
                    websocket,
                    {"type": "connected", "timestamp": time.time()},
                )

                while True:
                    data = await websocket.receive_json()
                    await self._handle_websocket_message(websocket, data)

            except WebSocketDisconnect:
                await self.manager.disconnect(websocket)
            except Exception:
                await self.manager.disconnect(websocket)

    async def _handle_websocket_message(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        msg_type = data.get("type", "")

        if msg_type == "chat":
            session_id = data.get("session_id")
            content = data.get("content", "")

            session = await self._get_or_create_session(session_id)
            user_msg = UserMessage(role=MessageRole.USER, content=content)
            session.app_state.add_message(user_msg)

            await self.manager.send_personal(
                websocket,
                {"type": "chat_started", "session_id": session.app_state.session_id},
            )

            async for chunk in self._stream_chat(session, content):
                await self.manager.send_personal(
                    websocket,
                    {"type": "chat_chunk", "content": chunk},
                )

            await self.manager.send_personal(
                websocket,
                {"type": "chat_complete", "session_id": session.app_state.session_id},
            )

        elif msg_type == "ping":
            await self.manager.send_personal(
                websocket,
                {"type": "pong", "timestamp": time.time()},
            )

        elif msg_type == "get_state":
            session_id = data.get("session_id")
            if session_id and session_id in self.sessions:
                s = self.sessions[session_id]
                await self.manager.send_personal(
                    websocket,
                    {
                        "type": "state",
                        "session_id": session_id,
                        "cwd": s.app_state.cwd,
                        "message_count": len(s.app_state.messages),
                        "is_running": s.app_state.is_running,
                        "token_usage": {
                            "input_tokens": s.app_state.token_usage.input_tokens,
                            "output_tokens": s.app_state.token_usage.output_tokens,
                        },
                        "cost": s.app_state.cost_info.total_cost,
                    },
                )

    async def _get_or_create_session(self, session_id: str | None) -> ActiveSession:
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]

        config = load_config()
        cwd = os.getcwd()
        model = config.get_active_model()

        persist_dir = os.path.expanduser("~/.openlaoke/sessions")
        os.makedirs(persist_dir, exist_ok=True)
        persist_path = os.path.join(persist_dir, f"session_{int(time.time())}.json")

        app_state = create_app_state(cwd=cwd, model=model, persist_path=persist_path)
        app_state.session_config.model = model
        app_state.multi_provider_config = config.providers
        app_state.app_config = config

        registry = ToolRegistry()
        register_all_tools(registry)

        proxy_url = get_proxy_url(config)
        api = MultiProviderClient(config.providers, proxy=proxy_url)

        new_session_id = app_state.session_id
        session = ActiveSession(
            app_state=app_state,
            registry=registry,
            api=api,
            config=config,
        )
        self.sessions[new_session_id] = session
        return session

    async def _send_message(
        self, session: ActiveSession, content: str
    ) -> tuple[AssistantMessage, TokenUsage, CostInfo]:
        system_prompt = build_system_prompt(
            session.app_state, session.registry.get_all_for_prompt()
        )
        messages = [{"role": "user", "content": content}]
        tools = session.registry.get_all_for_prompt()

        response, usage, cost = await session.api.send_message(
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            max_tokens=session.config.max_tokens,
            temperature=session.config.temperature,
        )

        session.app_state.accumulate_tokens(usage)
        session.app_state.accumulate_cost(cost)

        await self.manager.broadcast(
            {
                "type": "message_complete",
                "session_id": session.app_state.session_id,
                "usage": {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                },
                "cost": cost.total_cost,
            }
        )

        return response, usage, cost

    async def _stream_chat(self, session: ActiveSession, content: str) -> AsyncIterator[str]:
        system_prompt = build_system_prompt(
            session.app_state, session.registry.get_all_for_prompt()
        )
        messages = [
            {"role": msg.role.value, "content": msg.content} for msg in session.app_state.messages
        ]
        tools = session.registry.get_all_for_prompt()

        try:
            async for text, usage, cost in session.api.stream_message(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                max_tokens=session.config.max_tokens,
                temperature=session.config.temperature,
            ):
                if text:
                    yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"

                if usage and cost:
                    session.app_state.accumulate_tokens(usage)
                    session.app_state.accumulate_cost(cost)
                    yield f"data: {json.dumps({'type': 'usage', 'usage': {'input_tokens': usage.input_tokens, 'output_tokens': usage.output_tokens}, 'cost': cost.total_cost})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    def run(self) -> None:
        import uvicorn

        print(f"Starting OpenLaoKe Web UI on http://{self.host}:{self.port}")
        print(f"Access from LAN at http://<your-ip>:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")


def create_web_ui(
    host: str = "0.0.0.0",
    port: int = 8080,
    cors_origins: list[str] | None = None,
) -> WebUI:
    return WebUI(host=host, port=port, cors_origins=cors_origins)
