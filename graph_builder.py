import os
import json
import difflib
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    RemoveMessage,
    ToolMessage,
)
from api.schemas import ChatbotState
from data.db import get_products_by_title, list_tag_categories, search_products_hybrid
from tools.qa import TOOLS
from prompts import system_prompt
from utils.llm_provider import get_llm


load_dotenv(".env")


def build_graph(checkpointer=None):
    llm = get_llm()

    summary_trigger_turns = int(os.getenv("SUMMARY_TRIGGER_TURNS", "8"))
    summary_keep_turns = int(os.getenv("SUMMARY_KEEP_TURNS", "3"))
    summary_max_chars = int(os.getenv("SUMMARY_MAX_CHARS", "1200"))
    if summary_keep_turns >= summary_trigger_turns:
        summary_keep_turns = max(1, summary_trigger_turns - 1)

    def _split_turns(messages: list[BaseMessage]) -> list[list[BaseMessage]]:
        turns: list[list[BaseMessage]] = []
        current: list[BaseMessage] = []
        for msg in messages:
            if isinstance(msg, HumanMessage) and current:
                turns.append(current)
                current = []
            current.append(msg)
        if current:
            turns.append(current)
        return turns

    def _flatten(turns: list[list[BaseMessage]]) -> list[BaseMessage]:
        flattened: list[BaseMessage] = []
        for turn in turns:
            flattened.extend(turn)
        return flattened

    def _message_to_text(msg: BaseMessage) -> str | None:
        if isinstance(msg, HumanMessage):
            role = "User"
        elif isinstance(msg, AIMessage):
            role = "Assistant"
        elif isinstance(msg, ToolMessage):
            role = "Data"
        else:
            return None

        content = msg.content
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    parts.append(str(part["text"]))
            content = " ".join(part for part in parts if part)

        if not content:
            return None
        return f"{role}: {content}"

    def _tool_payload(message: ToolMessage) -> dict | None:
        content = message.content
        if isinstance(content, dict):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    parts.append(str(part["text"]))
            content = " ".join(p for p in parts if p).strip()
        if isinstance(content, str):
            try:
                return json.loads(content)
            except Exception:
                return None
        return None

    def _render_for_summary(messages: list[BaseMessage]) -> str:
        lines: list[str] = []
        for msg in messages:
            line = _message_to_text(msg)
            if line:
                lines.append(line)
        return "\n".join(lines)

    def _needs_summary(state: ChatbotState) -> str:
        turns = _split_turns(state["messages"])
        return "summarize" if len(turns) > summary_trigger_turns else "assistant"

    def _data_driven_tool_filter(text: str, tools: list[str]) -> list[str]:
        if not text or not tools:
            return tools

        tool_set = set(tools)
        if (
            "get_product_by_name" not in tool_set
            or "get_products_in_category" not in tool_set
        ):
            return tools

        text_lower = text.lower()
        product_hit = False
        category_hit = False

        try:
            products = get_products_by_title(text, limit=1)
        except Exception:
            products = []

        if products:
            product_hit = True
        else:
            try:
                candidates = search_products_hybrid(text, limit=1)
            except Exception:
                candidates = []

            if candidates:
                candidate = candidates[0]
                title = (candidate.get("title") or "").lower()
                if title and title in text_lower:
                    product_hit = True
                elif candidate.get("exact_title_match"):
                    product_hit = True

        try:
            categories = list_tag_categories()
        except Exception:
            categories = []

        for category in categories:
            cat = (category or "").lower().strip()
            if cat and cat in text_lower:
                category_hit = True
                break

        print(
            "DEBUG: Data-driven routing product_hit="
            f"{product_hit} category_hit={category_hit}"
        )

        if product_hit and not category_hit:
            return [t for t in tools if t != "get_products_in_category"]
        if category_hit and not product_hit:
            return [t for t in tools if t != "get_product_by_name"]
        return tools

    async def tool_retriever(state: ChatbotState) -> dict:
        print("--- Checking tool relevance... ---")
        last_message = state["messages"][-1].content
        if not isinstance(last_message, str):
            last_message = str(last_message)

        # 1. Immediate Bypass for Small Talk (Zero-cost filter)
        small_talk_keywords = {
            "hi",
            "hello",
            "thanks",
            "thank you",
            "bye",
            "ok",
            "okay",
            "cool",
            "hey",
            "nice",
        }
        clean_msg = last_message.lower().strip().strip("?!.")

        if clean_msg in small_talk_keywords:
            print(f"DEBUG: Small talk detected ('{clean_msg}'). Skipping tools.")
            return {"retrieved_tools": []}

        # 2. Knowledge Base Check: If the question is about a product we already know, skip tool retrieval
        attribute_keywords = {
            "dimension",
            "dimensions",
            "SKU",
            "price",
            "stock",
            "weight",
            "specs",
            "shipping",
            "return",
            "warranty",
            "policy",
        }
        kb = state.get("knowledge_base", {})
        known_products = [
            k.split("product:", 1)[1].lower()
            for k in kb.keys()
            if k.startswith("product:")
        ]
        msg_lower = last_message.lower()

        print(f"DEBUG: KB check - Question: '{msg_lower}' | Known: {known_products}")

        # Fuzzy match product names
        mentions_known = any(p in msg_lower for p in known_products)
        if not mentions_known:
            # Check for close matches in words
            words = msg_lower.replace("?", "").split()
            for p in known_products:
                if difflib.get_close_matches(p, [msg_lower], n=1, cutoff=0.7) or any(
                    difflib.get_close_matches(p, [w], n=1, cutoff=0.8) for w in words
                ):
                    mentions_known = True
                    break

        # Check if the message is just an attribute/pronoun query
        msg_words = msg_lower.replace("?", "").split()
        has_attr_fuzzy = any(
            difflib.get_close_matches(attr, msg_words, n=1, cutoff=0.8)
            for attr in attribute_keywords
        )
        is_attr_only = all(
            word in attribute_keywords
            or word
            in {
                "what",
                "is",
                "the",
                "how",
                "much",
                "it",
                "that",
                "of",
                "show",
                "me",
                "tell",
                "for",
                "any",
                "specs",
                "details",
            }
            or any(
                difflib.get_close_matches(attr, [word], n=1, cutoff=0.8)
                for attr in attribute_keywords
            )
            for word in msg_words
        )

        if mentions_known or (is_attr_only and len(known_products) > 0):
            print(
                f"DEBUG: Fact found in Knowledge Base (Fuzzy Match). Blocking tool retrieval."
            )
            return {"retrieved_tools": []}

        # Return all tools (let LLM decide based on context)
        tool_names = [t.name for t in TOOLS]
        filtered_tools = _data_driven_tool_filter(last_message, tool_names)
        print(f"DEBUG: Relevant tools: {filtered_tools}")
        return {"retrieved_tools": filtered_tools}

    async def assistant(state: ChatbotState) -> dict:
        kb = state.get("knowledge_base", {})
        print(f"DEBUG: Assistant entering with KB keys: {list(kb.keys())}")
        print("--- Assistant thinking... ---")

        last_message = state["messages"][-1] if state["messages"] else None
        if isinstance(last_message, ToolMessage):
            payload = _tool_payload(last_message)
            if isinstance(payload, dict) and payload.get("type") == "review_summary":
                summary = (payload.get("summary") or "").strip()
                if summary:
                    return {"messages": [AIMessage(content=summary)]}
                return {
                    "messages": [
                        AIMessage(
                            content=(
                                "I couldn't find enough review details to summarize. "
                                "Would you like to check a different product?"
                            )
                        )
                    ]
                }

        # Detect if this is the very first turn
        is_not_first_turn = len(state["messages"]) > 1 or state.get("summary")

        retrieved_names = state.get("retrieved_tools", [])
        available_tools = [t for t in TOOLS if t.name in retrieved_names]

        full_system_content = system_prompt

        if is_not_first_turn:
            full_system_content += (
                "\n\n--- TURN STATUS ---\n"
                "This is NOT the first message. DO NOT include 'Welcome to our store!'."
            )

        # Dynamic tool binding
        if available_tools:
            llm_with_tools = llm.bind_tools(available_tools)
        else:
            # If no tools are relevant, allow the LLM to speak freely (conversational filler)
            llm_with_tools = llm
            full_system_content += (
                "\n\nGUIDE: No specific data tools are required for this turn. "
                "If the user is just saying hello, thank you, or making small talk, "
                "respond naturally and helpfully without calling any tools."
            )

        summary = state.get("summary")
        if summary:
            full_system_content += (
                f"\n\n--- CONVERSATION SUMMARY ---\n"
                f"{summary}\n"
                f"---------------------------\n"
                "Note: The conversation is already in progress. Do NOT repeat the welcome message."
            )

        kb = state.get("knowledge_base", {})
        if kb:
            kb_text = json.dumps(kb, indent=2)
            full_system_content += (
                f"\n\n--- LATEST KNOWN FACTS (KNOWLEDGE BASE) ---\n"
                "You ALREADY HAVE the following data. If the user asks for anything "
                "contained below, answer directly from this data. DO NOT call a tool "
                "if the data is already here.\n"
                f"{kb_text}\n"
                "------------------------------------------"
            )

        messages = [SystemMessage(content=full_system_content)] + state["messages"]
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    async def summarize(state: ChatbotState) -> dict:
        turns = _split_turns(state["messages"])
        if len(turns) <= summary_keep_turns:
            return {}

        turns_to_summarize = turns[:-summary_keep_turns]

        summary_input = _render_for_summary(_flatten(turns_to_summarize))
        if not summary_input.strip() and not state.get("summary"):
            return {}

        summary_system_prompt = (
            "You are a summarization assistant. Update the running summary of a "
            "customer support chat. Preserve user preferences, constraints, "
            "product interests, decisions, and unresolved questions. "
            "CRITICAL: Keep specific product data (price, stock, features) that has already been retrieved "
            "so the agent doesn't need to call tools for the same info again. "
            "Avoid technical tool call IDs. Write plain text, no bullets."
        )
        if summary_max_chars > 0:
            summary_system_prompt += f" Keep it under {summary_max_chars} characters."

        summary_prompt = (
            f"Existing summary:\n{state.get('summary') or ''}\n\n"
            f"New conversation to summarize:\n{summary_input}\n\n"
            "Updated summary:"
        )
        summary_response = await llm.ainvoke(
            [
                SystemMessage(content=summary_system_prompt),
                HumanMessage(content=summary_prompt),
            ]
        )
        new_summary = (summary_response.content or "").strip()
        if summary_max_chars > 0 and len(new_summary) > summary_max_chars:
            new_summary = new_summary[:summary_max_chars].rstrip()

        # Correctly remove the summarized messages using RemoveMessage
        messages_to_remove = [
            RemoveMessage(id=m.id) for m in _flatten(turns_to_summarize) if m.id
        ]

        return {"summary": new_summary, "messages": messages_to_remove}

    tool_node = ToolNode(TOOLS)

    async def debug_tool_node(state: ChatbotState) -> dict:
        messages = state["messages"]
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                for tool_call in last_message.tool_calls:
                    print(
                        f"DEBUG: Executing tool: {tool_call['name']} with args: {tool_call['args']}"
                    )
            else:
                print("DEBUG: Executing tools...")
        else:
            print("DEBUG: Executing tools...")

        result = await tool_node.ainvoke(state)

        # Log results and Extract Knowledge (Latest Known Facts)
        new_knowledge = {}
        for msg in result.get("messages", []):
            if isinstance(msg, ToolMessage):
                content_preview = (
                    str(msg.content)[:200] + "..."
                    if len(str(msg.content)) > 200
                    else str(msg.content)
                )
                print(f"DEBUG: Tool {msg.name} returned: {content_preview}")

                # Knowledge Extraction Logic
                payload = _tool_payload(msg)
                if isinstance(payload, dict):
                    # Cache specific product details
                    if payload.get("type") == "product_details" and payload.get(
                        "items"
                    ):
                        for item in payload["items"]:
                            name = item.get("title")
                            if name:
                                new_knowledge[f"product:{name}"] = item
                    # Cache review summaries
                    elif payload.get("type") == "review_summary":
                        # We need to find which product this was for from the tool call
                        last_aimsg = state["messages"][-1]
                        if isinstance(last_aimsg, AIMessage):
                            for tc in last_aimsg.tool_calls:
                                if tc["id"] == msg.tool_call_id:
                                    pname = tc["args"].get("product_name")
                                    if pname:
                                        new_knowledge[f"reviews:{pname}"] = payload.get(
                                            "summary"
                                        )

        return {**result, "knowledge_base": new_knowledge}

    graph_builder = StateGraph(ChatbotState)
    graph_builder.add_node(
        "preprocess",
        lambda state: {"knowledge_base": state.get("knowledge_base") or {}},
    )
    graph_builder.add_node("tool_retriever", tool_retriever)
    graph_builder.add_node("summarize", summarize)
    graph_builder.add_node("assistant", assistant)
    graph_builder.add_node("tools", debug_tool_node)

    graph_builder.add_edge(START, "preprocess")
    graph_builder.add_edge("preprocess", "tool_retriever")

    graph_builder.add_conditional_edges(
        "tool_retriever",
        _needs_summary,
        {"summarize": "summarize", "assistant": "assistant"},
    )
    graph_builder.add_edge("summarize", "assistant")
    graph_builder.add_conditional_edges(
        "assistant", tools_condition, {"tools": "tools", "__end__": END}
    )
    graph_builder.add_edge("tools", "assistant")

    return graph_builder.compile(checkpointer=checkpointer)
