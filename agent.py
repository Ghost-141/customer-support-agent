import os
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from prompts import system_prompt
from db import search_products_hybrid

ollama_model = OpenAIChatModel(
    model_name="llama3.2:latest",
    provider=OllamaProvider(base_url="http://localhost:11434/v1"),
)

# os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"


agent = Agent(
    model=ollama_model,
    system_prompt=system_prompt,
    model_settings={"temperature": 0.0, "max_tokens": 500},
)


@agent.tool_plain
def get_query_data(query: str) -> str:
    rows = search_products_hybrid(query, limit=5)
    if not rows:
        return "No matching products found."
    lines = []
    for p in rows:
        title = p.get("title", "Unknown")
        price = p.get("price")
        rating = p.get("avg_rating")
        stock = p.get("stock")
        parts = [title]
        if price is not None:
            parts.append(f"Price: {price}")
        if rating is not None:
            parts.append(f"Rating: {rating:.2f}")
        if stock is not None:
            parts.append(f"Stock: {stock}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)
