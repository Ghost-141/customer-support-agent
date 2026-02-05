from fastapi import APIRouter, Request, HTTPException, Query, Depends
from fastapi.background import BackgroundTasks
from api.services.whatsapp import send_whatsapp_message
from dotenv import load_dotenv
import os
from agent import run_agent
from api.services.dependency import get_db_pool
from psycopg_pool import AsyncConnectionPool

load_dotenv()

whatsapp_router = APIRouter()

MAX_MESSAGE_LENGTH = os.getenv("MAX_MESSAGE_LENGTH")


@whatsapp_router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    pool: AsyncConnectionPool = Depends(get_db_pool),
):
    data = await request.json()
    background_tasks.add_task(process_whatsapp_message, data, pool)
    return {"status": "recieved"}


async def process_whatsapp_message(data: dict, pool: AsyncConnectionPool):
    entry = data.get("entry", [{}])[0]
    changes = entry.get("changes", [{}])[0]
    value = changes.get("value", {})
    if "messages" not in value:
        return
    messages = value["messages"]
    if not messages:
        return
    message = messages[0]
    from_number = message["from"]
    user_text = message["text"]["body"]
    print(f"User text: {user_text}")

    if len(user_text) > int(MAX_MESSAGE_LENGTH):
        send_whatsapp_message(
            to=from_number,
            body=f"Your message is too long. Please try again with a shorter message.",
        )
        return {"status": "message too long"}

    response = await run_agent(user_text, from_number, pool)

    send_whatsapp_message(to=from_number, body=response)


@whatsapp_router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="shub.verify_token"),
):
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN")
    if hub_mode == "subscribe" and hub_challenge and hub_verify_token == verify_token:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="verification failed")
