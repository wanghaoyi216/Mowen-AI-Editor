"""Services package.

Re-exports the in-process event bus for Agent streaming (SSE).
"""
from app.services.agent_event_bus import AgentEvent, AgentEventBus, bus

__all__ = ["bus", "AgentEvent", "AgentEventBus"]
