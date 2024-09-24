import asyncio
import json
import uuid

from dotenv import load_dotenv
from memory import ConversationMemory
from openai import OpenAI
from websocket import ConnectionManager

from ouro import Ouro

load_dotenv()

client = OpenAI()


async def send_typing_status(user_id, conversation, supabase):
    channel = supabase.channel(f"{conversation.id}-presence")

    def on_subscribe(status, err):
        print("on_subscribe", status, err)
        # if status == RealtimeSubscribeStates.SUBSCRIBED:
        channel.send_broadcast(
            "typing",
            {
                "user_id": user_id,
                "active": True,
            },
        )

    channel.subscribe(on_subscribe)


async def handle_message(message: str, ouro: Ouro, manager: ConnectionManager):
    """
    Handle incoming messages from the backend (e.g. new messages from user conversations). Stateless and async.
    """
    # The user id of the assistant
    agent_user_id = ouro.user.id

    try:
        data = json.loads(message)
    except:
        print("Failed to parse message:", message)
        return

    if "event" in data and data["event"] == "new-message":
        print("Parsed message:", data)

        conversation_id = data["data"]["conversation_id"]
        incoming_message = data["data"]["text"]
        websocket = manager.active_connections.get(agent_user_id, None)

        # Get the conversation
        conversation = ouro.conversations.retrieve(conversation_id)
        if conversation is None:
            return

        # If message is coming from self, ignore
        if data["data"]["user_id"] == agent_user_id:
            return

        # Send typing status to the conversation channel
        # asyncio.create_task(send_typing_status(user_id, conversation, ouro.supabase))

        # TODO: Handle group conversations
        # Get the recipient's user id
        recipient_id = (
            str(conversation.metadata.members[0])
            if conversation.metadata.members[0] != agent_user_id
            else str(conversation.metadata.members[1])
        )

        # Load the messages
        messages = conversation.messages.list()
        messages_formatted = [
            {
                "role": "user" if message["user_id"] != agent_user_id else "assistant",
                "content": message["text"],
            }
            for message in messages
        ]

        memory = ConversationMemory(short_term_size=5)
        for m in messages_formatted:
            memory.add_message(m)
        context = memory.build_context(incoming_message)
        # print(context)

        # Get the response from the model
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=context,
            stream=True,
        )

        message = ""
        message_id = str(uuid.uuid4())
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                message += content
                if websocket:
                    # Send each chunk back to the server
                    await websocket.send(
                        json.dumps(
                            {
                                "event": "llm-response",
                                "recipient_id": recipient_id,
                                "data": {
                                    "content": content,
                                    "id": message_id,
                                    "user_id": agent_user_id,
                                },
                            }
                        )
                    )
                    # Artificially wait a few ms to simulate typing
                    await asyncio.sleep(0.001)

        # Send a message to indicate the stream has ended
        if websocket:
            await websocket.send(
                json.dumps(
                    {
                        "event": "llm-response-end",
                        "recipient_id": recipient_id,
                        "data": {"id": message_id, "user_id": agent_user_id},
                    }
                )
            )

        # Write the response to the conversation
        content = ouro.posts.Content(text=message)
        created = conversation.messages.create(
            id=message_id,
            text=content.to_dict()["text"],
            json=content.to_dict()["json"],
        )

    else:
        print("Backend response:", data)
