from agent import agent
from pydantic_ai.usage import UsageLimits
from langgraph.types import StreamWriter
from langgraph.graph import StateGraph, START, END
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from schemas import ChatbotState


MAX_HISTORY_MESSAGE = 5


async def main_agent(state: ChatbotState, writer: StreamWriter):
    message_history: list[ModelMessage] = []
    message_history = state["message"][-MAX_HISTORY_MESSAGE:]

    for message in message_history:
        message_history.extend(ModelMessagesTypeAdapter.validate_json(message))

    result = await agent.run(
        state["lastet_user_message"],
        message_history=message_history,
        usage_limits=UsageLimits(request_limit=3),
    )

    writer(result.data)

    return {"message": [result.new_messages_json()]}


def build_graph(checkpointer=None):
    graph_builder = StateGraph(ChatbotState)

    graph_builder.add_node("agent", main_agent)
    graph_builder.add_edge(START, "agent")
    graph = graph_builder.compile(checkpointer=checkpointer)
    return graph
