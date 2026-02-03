import os
import asyncio
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from dotenv import load_dotenv
from graph_builder import build_graph
from db import _build_db_url


async def run_local_chat(graph, user_message: str, from_number: str):
    """
    Example CLI loop for local development and debugging.
    """
    thread_id = from_number
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
    return result["messages"][-1].content


async def run_agent(user_message: str, from_number: str) -> str:
    load_dotenv()
    conn_info = _build_db_url()
    async with AsyncConnectionPool(
        conninfo=conn_info,
        max_size=20,
        kwargs={
            "autocommit": True,
            "prepare_threshold": None,  # Disable automatic prepared statements
            "row_factory": dict_row,
        },
    ) as pool:
        async with pool.connection() as conn:
            memory = AsyncPostgresSaver(conn)
            await memory.setup()

            # Build and run the graph
            graph = build_graph(checkpointer=memory)

            # Properly consume the async generator
            response = await run_local_chat(graph, user_message, from_number)
            print(f"Agent response: {response}")
            return response


if __name__ == "__main__":
    from_number = "12013"  # Use a fixed number for the conversation

    async def main_loop():
        while True:
            try:
                user_input = input("User: ")
                if user_input.lower() in ["quit", "exit", "q"]:
                    print("Goodbye!")
                    break

                await run_agent(user_input, from_number)
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
                import traceback

                traceback.print_exc()

    # Run the async main loop
    asyncio.run(main_loop())
