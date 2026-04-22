"""FastAPI-based HTTP API server with WebSocket support."""

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
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from openlaoke.core.config_wizard import get_proxy_url
from openlaoke.core.insomnia_engine import InsomniaEngine
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
    insomnia_engine: InsomniaEngine | None = None
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


class Server:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 3000,
        cors_origins: list[str] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.cors_origins = cors_origins or [
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080",
        ]
        self.app = FastAPI(
            title="OpenLaoKe API",
            description="Open-source AI coding assistant API",
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

        @app.post("/api/insomnia/enable")
        async def enable_insomnia(session_id: str | None = None) -> dict[str, Any]:
            session = await self._get_or_create_session(session_id)
            if not session.insomnia_engine:
                session.insomnia_engine = InsomniaEngine(session.app_state)
                session.app_state._insomnia_engine = session.insomnia_engine
            await session.insomnia_engine.start()
            return {"success": True, "message": "Insomnia mode enabled"}

        @app.post("/api/insomnia/disable")
        async def disable_insomnia(session_id: str | None = None) -> dict[str, Any]:
            session = await self._get_or_create_session(session_id)
            if session.insomnia_engine:
                await session.insomnia_engine.stop()
            return {"success": True, "message": "Insomnia mode disabled"}

        @app.post("/api/insomnia/add")
        async def add_insomnia_task(
            prompt: str, session_id: str | None = None, max_iterations: int | None = None
        ) -> dict[str, Any]:
            session = await self._get_or_create_session(session_id)
            if not session.insomnia_engine:
                session.insomnia_engine = InsomniaEngine(session.app_state)
                session.app_state._insomnia_engine = session.insomnia_engine
            task_id = await session.insomnia_engine.add_task(prompt, max_iterations)
            return {"success": True, "task_id": task_id}

        @app.get("/api/insomnia/status")
        async def insomnia_status(session_id: str | None = None) -> dict[str, Any]:
            session = await self._get_or_create_session(session_id)
            if not session.insomnia_engine:
                return {"running": False, "queue_size": 0}
            return session.insomnia_engine.get_status()

        @app.get("/api/insomnia/log")
        async def insomnia_log(
            session_id: str | None = None, limit: int = 50
        ) -> list[dict[str, Any]]:
            session = await self._get_or_create_session(session_id)
            if not session.insomnia_engine:
                return []
            return session.insomnia_engine.get_log(limit)

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

        insomnia_engine = InsomniaEngine(app_state)
        app_state._insomnia_engine = insomnia_engine

        new_session_id = app_state.session_id
        session = ActiveSession(
            app_state=app_state,
            registry=registry,
            api=api,
            config=config,
            insomnia_engine=insomnia_engine,
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

        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")


def create_server(
    host: str = "localhost",
    port: int = 3000,
    cors_origins: list[str] | None = None,
) -> Server:
    return Server(host=host, port=port, cors_origins=cors_origins)
