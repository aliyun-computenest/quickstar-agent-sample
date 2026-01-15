# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import Dict, Optional
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.services.agent_state.state_service import InMemoryStateService
from agentscope_runtime.engine.services.session_history.session_history_service import InMemorySessionHistoryService
from agentscope_runtime.engine.services.sandbox.sandbox_service import SandboxService
from agentscope_runtime.adapters.agentscope.memory import AgentScopeSessionHistoryMemory
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit
from agentscope.pipeline import stream_printing_messages
import os

logger = logging.getLogger(__name__)

class UserSession:
    """Represents a user session with its own services and agent"""
    
    def __init__(self, user_id: str, session_id: str):
        self.user_id = user_id
        self.session_id = session_id
        self.agent_app = None
        self.agent = None
        self.state_service = None
        self.session_service = None
        self.sandbox_service = None
        self.last_accessed = asyncio.get_event_loop().time()
        
    async def initialize(self):
        """Initialize the user session with all required services"""
        self.agent_app = AgentApp(
            app_name=f"Friday-{self.user_id}",
            app_description=f"A helpful assistant for user {self.user_id}",
        )
        
        # Initialize services
        self.state_service = InMemoryStateService()
        self.session_service = InMemorySessionHistoryService()
        self.sandbox_service = SandboxService(base_url='http://47.239.1.29:8000', bearer_token='sk-chstlbmhba')

        await self.state_service.start()
        await self.session_service.start()
        await self.sandbox_service.start()
        
        # Set up the agent app callbacks
        @self.agent_app.init
        async def init_func(self):
            # Services are already initialized above
            pass
            
        @self.agent_app.shutdown
        async def shutdown_func(self):
            await self.state_service.stop()
            await self.session_service.stop()
            await self.sandbox_service.stop()
            
        @self.agent_app.query(framework="agentscope")
        async def query_func(self, msgs, request):
            session_id = request.session_id
            user_id = request.user_id
            
            # Update last accessed time
            self.last_accessed = asyncio.get_event_loop().time()
            
            state = await self.state_service.export_state(
                session_id=session_id,
                user_id=user_id,
            )
            
            # Get sandbox
            try:
                sandboxes = self.sandbox_service.connect(
                    session_id=session_id,
                    user_id=user_id,
                    sandbox_types=["browser"],
                )
                
                if sandboxes:
                    sandbox = sandboxes[0]
                    
                    browser_tools = [
                        sandbox.browser_navigate,
                        sandbox.browser_take_screenshot,
                        sandbox.browser_snapshot,
                        sandbox.browser_click,
                        sandbox.browser_type,
                    ]
                    
                    toolkit = Toolkit()
                    for tool in browser_tools:
                        toolkit.register_tool_function(tool)
                        
                    # Import SYSTEM_PROMPT here to avoid circular imports
                    from prompts import SYSTEM_PROMPT
                    
                    agent = ReActAgent(
                        name=f"Friday-{user_id}",
                        model=DashScopeChatModel(
                            "qwen-max",
                            api_key=os.getenv("DASHSCOPE_API_KEY"),
                            enable_thinking=True,
                            stream=True,
                        ),
                        sys_prompt=SYSTEM_PROMPT,
                        toolkit=toolkit,
                        memory=AgentScopeSessionHistoryMemory(
                            service=self.session_service,
                            session_id=session_id,
                            user_id=user_id,
                        ),
                        formatter=DashScopeChatFormatter(),
                    )
                    
                    if state:
                        agent.load_state_dict(state)
                        
                    async for msg, last in stream_printing_messages(
                        agents=[agent],
                        coroutine_task=agent(msgs),
                    ):
                        yield msg, last
                        
                    state = agent.state_dict()
                    await self.state_service.save_state(
                        user_id=user_id,
                        session_id=session_id,
                        state=state,
                    )
                else:
                    raise Exception("Failed to connect to sandbox")
            except Exception as e:
                logger.error(f"Error in query_func for user {user_id}: {str(e)}")
                raise
                
        # Start the agent app
        def run_agent_app():
            self.agent_app.run(host="127.0.0.1", port=0)  # Port 0 means auto-assign
            
        # We won't start the app in a thread like the original code since we're managing it differently
        
    async def cleanup(self):
        """Clean up the user session resources"""
        if self.agent_app:
            try:
                # Call shutdown function
                if hasattr(self.agent_app, 'shutdown'):
                    await self.agent_app.shutdown()
            except Exception as e:
                logger.error(f"Error during agent app shutdown: {str(e)}")
                
        if self.sandbox_service:
            try:
                await self.sandbox_service.stop()
            except Exception as e:
                logger.error(f"Error stopping sandbox service: {str(e)}")
                
        if self.session_service:
            try:
                await self.session_service.stop()
            except Exception as e:
                logger.error(f"Error stopping session service: {str(e)}")
                
        if self.state_service:
            try:
                await self.state_service.stop()
            except Exception as e:
                logger.error(f"Error stopping state service: {str(e)}")


class MultiUserAgentManager:
    """Manages multiple user sessions"""
    
    def __init__(self, max_sessions: int = 100, session_timeout: int = 3600):
        self.sessions: Dict[str, UserSession] = {}
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout  # Timeout in seconds
        self.lock = asyncio.Lock()
        # Add a background task for periodic cleanup
        self.cleanup_task = None
        self.is_running = False

    async def start_cleanup_task(self):
        """Start the periodic cleanup task"""
        if not self.is_running:
            self.is_running = True
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop_cleanup_task(self):
        """Stop the periodic cleanup task"""
        self.is_running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

    async def _periodic_cleanup(self):
        """Periodically clean up expired sessions"""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Run cleanup every 5 minutes
                await self._cleanup_expired_sessions()
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {str(e)}")

    def _get_session_key(self, user_id: str, session_id: str) -> str:
        """Generate a unique key for a user session"""
        return f"{user_id}:{session_id}"
        
    async def get_or_create_session(self, user_id: str, session_id: str) -> UserSession:
        """Get an existing session or create a new one"""
        async with self.lock:
            session_key = self._get_session_key(user_id, session_id)
            
            # Clean up expired sessions if we're at capacity
            if len(self.sessions) >= self.max_sessions:
                await self._cleanup_expired_sessions()
                
            # If still at capacity, remove the oldest session
            if len(self.sessions) >= self.max_sessions:
                await self._remove_oldest_session()
                
            # Return existing session if it exists
            if session_key in self.sessions:
                session = self.sessions[session_key]
                session.last_accessed = asyncio.get_event_loop().time()
                return session
                
            # Create new session
            session = UserSession(user_id, session_id)
            await session.initialize()
            self.sessions[session_key] = session
            return session
            
    async def get_session(self, user_id: str, session_id: str) -> Optional[UserSession]:
        """Get an existing session without creating a new one"""
        async with self.lock:
            session_key = self._get_session_key(user_id, session_id)
            return self.sessions.get(session_key)
            
    async def remove_session(self, user_id: str, session_id: str):
        """Remove and clean up a specific session"""
        async with self.lock:
            session_key = self._get_session_key(user_id, session_id)
            if session_key in self.sessions:
                session = self.sessions.pop(session_key)
                await session.cleanup()
                
    async def _cleanup_expired_sessions(self):
        """Remove expired sessions"""
        current_time = asyncio.get_event_loop().time()
        expired_keys = []
        
        for key, session in self.sessions.items():
            if current_time - session.last_accessed > self.session_timeout:
                expired_keys.append(key)
                
        for key in expired_keys:
            session = self.sessions.pop(key)
            await session.cleanup()
            
    async def _remove_oldest_session(self):
        """Remove the oldest session"""
        if not self.sessions:
            return
            
        oldest_key = None
        oldest_time = float('inf')
        
        for key, session in self.sessions.items():
            if session.last_accessed < oldest_time:
                oldest_time = session.last_accessed
                oldest_key = key
                
        if oldest_key:
            session = self.sessions.pop(oldest_key)
            await session.cleanup()
            
    async def cleanup_all_sessions(self):
        """Clean up all sessions"""
        async with self.lock:
            sessions_to_cleanup = list(self.sessions.values())
            self.sessions.clear()
            
            for session in sessions_to_cleanup:
                await session.cleanup()