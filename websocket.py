from typing import Dict

from fastapi import WebSocket, exceptions


# WebSocket connection manager for frontend clients
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        self.active_connections[client_id] = websocket

    async def disconnect(self, client_id: str):
        websocket = self.active_connections.pop(client_id, None)
        if websocket:
            try:
                await websocket.close()
            except exceptions.ConnectionClosed:
                pass  # The connection is already closed
            except Exception as e:
                print(f"Error closing WebSocket: {e}")
