import asyncio
from agents.qa import agent


async def main():
    print("Agent is ready. Type 'quit' to exit.")
    while True:
        user_input = input("User: ")
        if user_input.lower() in ("quit", "exit"):
            break

        try:
            result = await agent.run(user_input)
            print(f"Agent: {result.output}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
