import os
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_ollama import ChatOllama
from schemas import ChatbotState
from agents.qa import TOOLS


def build_graph(checkpointer=None):
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.2:latest"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0.0,
    )
    llm_with_tools = llm.bind_tools(TOOLS)

    async def assistant(state: ChatbotState) -> dict:
        response = await llm_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}

    graph_builder = StateGraph(ChatbotState)
    graph_builder.add_node("assistant", assistant)
    graph_builder.add_node("tools", ToolNode(TOOLS))
    graph_builder.add_edge(START, "assistant")
    graph_builder.add_conditional_edges(
        "assistant", tools_condition, {"tools": "tools", "__end__": END}
    )
    graph_builder.add_edge("tools", "assistant")

    return graph_builder.compile(checkpointer=checkpointer)
