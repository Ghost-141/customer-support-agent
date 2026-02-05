import os
import asyncio
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages import AIMessage
from psycopg_pool import AsyncConnectionPool
from dotenv import load_dotenv
from graph_builder import build_graph
from db_pool import create_async_pool


def _normalize_from_number(raw: str) -> str:
    # Keep only digits and a leading "+" if present to avoid collisions.
    if raw is None:
        return "unknown"
    raw = raw.strip()
    if not raw:
        return "unknown"
    leading_plus = raw.startswith("+")
    digits = "".join(ch for ch in raw if ch.isdigit())
    return f"+{digits}" if leading_plus else digits or "unknown"


def _build_thread_id(from_number: str, channel: str = "whatsapp") -> str:
    normalized = _normalize_from_number(from_number)
    return f"{channel}:{normalized}"


async def run_local_chat(graph, user_message: str, from_number: str):
    """
    Example CLI loop for local development and debugging.
    """
    thread_id = _build_thread_id(from_number)
    # LangSmith tracing configuration (set LANGCHAIN_API_KEY in your env)
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "Whatsapp Support Agent")

    # Get the current state from the graph using the thread_id
    config = {
        "configurable": {"thread_id": thread_id},
        "tags": ["support_agent", "whatsapp"],
        "metadata": {"from_number": from_number},
    }

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
    user_message: str, from_number: str, pool: AsyncConnectionPool
) -> str:
    async with pool.connection() as conn:
        # Handle clear command
        if user_message.strip() == "/clear":
            thread_id = _build_thread_id(from_number)
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
        response = await run_local_chat(graph, user_message, from_number)
        print(f"Agent response: {response}")
        return response


if __name__ == "__main__":
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
