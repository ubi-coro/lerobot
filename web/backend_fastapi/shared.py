"""
Shared state module for FastAPI backend
=======================================

Provides shared instances that need to be accessible across modules and
utilities for thread-safe interaction with the asyncio event loop.
"""

from __future__ import annotations

import asyncio
import socketio
from typing import Optional, Any

# Global Socket.IO instance and event loop
sio: Optional[socketio.AsyncServer] = None
_loop: Optional[asyncio.AbstractEventLoop] = None


def set_socketio(socketio_instance: socketio.AsyncServer):
    """Set the global Socket.IO instance"""
    global sio
    sio = socketio_instance


def get_socketio() -> Optional[socketio.AsyncServer]:
    """Get the global Socket.IO instance"""
    return sio


def set_event_loop(loop: asyncio.AbstractEventLoop):
    """Capture and store the main asyncio event loop for cross-thread scheduling."""
    global _loop
    _loop = loop


def get_event_loop() -> Optional[asyncio.AbstractEventLoop]:
    """Return the stored asyncio event loop, if any."""
    return _loop


def run_coro_threadsafe(coro):
    """Schedule an asyncio coroutine from any thread on the stored event loop.

    Silently no-ops if no loop is available or it's not running (e.g., during shutdown).
    """
    try:
        loop = get_event_loop() or asyncio.get_event_loop()
    except RuntimeError:
        # No default loop in this thread
        loop = get_event_loop()
    if not loop:
        return
    try:
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, loop)
    except Exception:
        # Ignore scheduling errors (e.g., loop closing during shutdown)
        pass


def emit_threadsafe(event: str, data: Any, *, room: Optional[str] = None, namespace: Optional[str] = None):
    """Emit a Socket.IO event from any thread using the stored asyncio loop.

    This avoids 'no current event loop' and 'coroutine was never awaited' errors
    when called from background threads.
    """
    if sio is None:
        return
    try:
        coro = sio.emit(event, data, room=room, namespace=namespace)
    except Exception:
        return
    run_coro_threadsafe(coro)
