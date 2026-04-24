import os
import sys
import asyncio
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from dotenv import load_dotenv
from graph_builder import build_graph
from data.db_pool import create_async_pool


def _normalize_from_number(raw: str) -> str:
    # Keep only digits and a leading "+" if present to avoid collisions.
    if raw is None:
        return "unknown"
    raw = raw.strip()
    if not raw:
        return "unknown"
    leading_plus = raw.startswith("+")
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return raw
    return f"+{digits}" if leading_plus else digits


def _build_thread_id(from_number: str, channel: str = "whatsapp") -> str:
    if channel == "telegram":
        # For telegram, from_number is already tg:chat_id
        return from_number
    if channel == "websocket":
        # For websocket, use the client_id as is to avoid stripping UUIDs/strings
        return f"{channel}:{from_number}"
    normalized = _normalize_from_number(from_number)
    return f"{channel}:{normalized}"


def _build_run_config(from_number: str, channel: str) -> tuple[str, dict]:
    thread_id = _build_thread_id(from_number, channel)
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", f"{channel.capitalize()} Support Agent")

    config = {
        "configurable": {"thread_id": thread_id},
        "tags": ["support_agent", channel],
        "metadata": {"from_number": from_number},
    }
    return thread_id, config


async def _table_exists(conn, table_name: str, schema: str = "public") -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            select exists(
                select 1
                from information_schema.tables
                where table_schema = %s
                  and table_name = %s
            ) as exists
            """,
            (schema, table_name),
        )
        row = await cur.fetchone()
        if not row:
            return False
        return bool(row.get("exists"))


async def run_local_chat(
    graph, user_message: str, from_number: str, channel: str = "whatsapp"
):
    """
    Example CLI loop for local development and debugging.
    """
    _, config = _build_run_config(from_number, channel)

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=user_message)],
        },
        config,
    )
    # Get all messages from the result
    all_messages = result["messages"]

    # Find the last HumanMessage (the one we just sent)
    last_human_idx = -1
    for i in range(len(all_messages) - 1, -1, -1):
        if isinstance(all_messages[i], HumanMessage):
            last_human_idx = i
            break

    # Extract all content from AIMessages following the last HumanMessage
    new_responses = []
    for msg in all_messages[last_human_idx + 1 :]:
        if isinstance(msg, AIMessage) and msg.content:
            new_responses.append(msg.content)

    return "\n\n".join(new_responses)


async def run_agent(
    user_message: str,
    from_number: str,
    pool: AsyncConnectionPool,
    channel: str = "whatsapp",
) -> str:
    async with pool.connection() as conn:
        # Handle clear command
        if user_message.strip() == "/clear":
            required_tables = [
                "checkpoints",
                "checkpoint_blobs",
                "checkpoint_writes",
            ]
            missing = []
            for table in required_tables:
                if not await _table_exists(conn, table):
                    missing.append(table)
            if missing:
                missing_list = ", ".join(missing)
                return (
                    "Checkpoint tables are missing: "
                    f"{missing_list}. Run the DB setup to create them."
                )
            thread_id = _build_thread_id(from_number, channel)
            await conn.execute(
                "DELETE FROM checkpoints WHERE thread_id = %s", (thread_id,)
            )
            await conn.execute(
                "DELETE FROM checkpoint_blobs WHERE thread_id = %s", (thread_id,)
            )
            await conn.execute(
                "DELETE FROM checkpoint_writes WHERE thread_id = %s", (thread_id,)
            )
            return "Conversation history cleared."

        memory = AsyncPostgresSaver(conn)
        await memory.setup()

        # Build and run the graph
        graph = build_graph(checkpointer=memory)

        # Properly consume the async generator
        response = await run_local_chat(graph, user_message, from_number, channel)
        print(f"Agent response: {response}")
        return response


if __name__ == "__main__":
    if sys.platform == "win32":
        # psycopg async doesn't work with ProactorEventLoop on Windows.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    from_number = input("From number: ").strip() or "unknown"

    async def main_loop():
        load_dotenv()
        print("Chat session started. Type '/clear' to reset conversation history.")

        async with create_async_pool() as pool:
            while True:
                try:
                    user_input = input("User: ")
                    if user_input.lower() in ["quit", "exit", "q"]:
                        print("Goodbye!")
                        break

                    await run_agent(user_input, from_number, pool)
                except KeyboardInterrupt:
                    print("\nGoodbye!")
                    break
                except Exception as e:
                    print(f"Error: {e}")
                    import traceback

                    traceback.print_exc()

    # Run the async main loop
    asyncio.run(main_loop())
