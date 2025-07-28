"""
Shared state module for FastAPI backend
=======================================

Provides shared instances that need to be accessible across modules.
"""

import socketio
from typing import Optional

# Global Socket.IO instance
sio: Optional[socketio.AsyncServer] = None

def set_socketio(socketio_instance: socketio.AsyncServer):
    """Set the global Socket.IO instance"""
    global sio
    sio = socketio_instance

def get_socketio() -> Optional[socketio.AsyncServer]:
    """Get the global Socket.IO instance"""
    return sio
