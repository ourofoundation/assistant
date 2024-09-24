import asyncio
import json
import os
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import uvicorn
import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, exceptions
from fastapi.middleware.cors import CORSMiddleware
from lib import handle_message
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from websocket import ConnectionManager

from ouro import Ouro

load_dotenv()


OURO_BACKEND_WS_URL = "ws://localhost:8003"
OURO_BACKEND_URL = "http://localhost:8003"


# Global flag to indicate WebSocket connection status
websocket_connected = asyncio.Event()
websocket_connection = None


manager = ConnectionManager()


async def subscribe_to_conversations(ouro):
    # Wait for the WebSocket connection to be established
    await websocket_connected.wait()

    response = ouro.client.get("/conversations/subscribe")
    data = response.json()

    if data["error"]:
        raise data["error"]
    else:
        print("Subscribed to changes:", data["data"])

    return data


# Connect to Node.js WebSocket server
async def connect_to_backend(ouro):
    user_id = ouro.user.id
    uri = f"{OURO_BACKEND_WS_URL}/ws/{user_id}"
    while True:
        try:
            # TODO: need to secure this connection
            async with websockets.connect(uri) as websocket:
                global websocket_connection
                websocket_connection = websocket
                print(f"Connected to backend: {ouro.user.email}")
                # Set the event to indicate the connection is established
                websocket_connected.set()
                # Add the connection to the manager
                await manager.connect(websocket, user_id)
                # Start the subscription task after establishing a ws connection
                await subscribe_to_conversations(ouro)
                while True:
                    try:
                        while True:
                            message = await websocket.recv()
                            await handle_message(message, ouro, manager)
                    except websockets.ConnectionClosed:
                        print("WebSocket connection closed unexpectedly")
                        raise  # Re-raise to trigger reconnection
        except websockets.ConnectionClosed:
            print("WebSocket connection closed")
        except Exception as e:
            print(f"Error in WebSocket connection: {e}")
        finally:
            websocket_connected.clear()
            await manager.disconnect(user_id)

        print(f"Retrying connection in 3 seconds...")
        await asyncio.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global backend_task, ouro

    ouro = Ouro(api_key=os.environ.get("OURO_API_KEY"))
    # Start the WebSocket connection task
    await connect_to_backend(ouro)

    yield

    # Close the WebSocket connection if it's still open
    global websocket_connection
    if websocket_connection:
        await websocket_connection.close()


# Initialize FastAPI app
app = FastAPI(
    lifespan=lifespan,
    title="Hermes Agent",
    description="Hermes chatbot",
    servers=[
        {
            "url": "https://hermes.ouro.foundation",
            "description": "Production environment",
        },
    ],
    terms_of_service="https://ouro.foundation/legal/terms",
    contact={
        "name": "Hermes",
        "url": "https://ouro.foundation/app/users/hermes",
        "email": "hermes@ouro.foundation",
    },
)


# Allow origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.environ.get("OURO_FRONTEND_URL", "http://localhost:3000"),
        os.environ.get("OURO_BACKEND_URL", "http://localhost:8003"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/agent")
async def root():
    return {"message": "hello world"}


@app.exception_handler(exceptions.RequestValidationError)
@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    print(f"The client sent invalid data!: {exc}")
    # exc_json = json.loads(exc.json())
    # response = {"message": [], "data": None}
    # for error in exc_json:
    #     response["message"].append(f"{error['loc']}: {error['msg']}")

    # return JSONResponse(response, status_code=422)


if __name__ == "__main__":
    uvicorn.run("server:app", port=8012, reload=True)
