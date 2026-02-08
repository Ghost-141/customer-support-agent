from langchain_core.tools import tool
from data.db import get_product_reviews as _get_product_reviews
from api.schemas import (
    ProductDetails,
    ProductDetailItem,
    ReviewItem,
    ReviewResults,
    ReviewResponse,
    CategoryList,
    CategoryProducts,
    ErrorResponse,
)
from langchain_core.messages import HumanMessage, SystemMessage
from utils.llm_provider import get_llm
from data.db import (
    get_products_by_title,
    get_products_by_category,
    list_tag_categories,
    search_products_hybrid,
)


@tool
def get_product_by_name(product_name: str) -> dict:
    """Fetch specifications, pricing, and stock status ONLY for a specific, known product name.

    Use this tool EXCLUSIVELY when the user asks about a concrete product title they already mentioned or know (e.g., "Essence Mascara", "kiwi").
    Do NOT use this tool for general product discovery, brand searches, or "find me" queries.
    This tool is strictly for retrieving data on a single, identified product.
    """
    # Try exact title match first
    products = get_products_by_title(product_name, limit=5)

    # If no exact match, fallback to hybrid search to be more helpful
    if not products:
        products = search_products_hybrid(product_name, limit=5)

    if not products:
        return ProductDetails(items=[]).model_dump()

    items = []
    for product in products:
        items.append(
            ProductDetailItem(
                id=product.get("id"),
                title=product.get("title"),
                brand=product.get("brand"),
                category=product.get("category"),
                price=product.get("price"),
                rating=product.get("rating"),
                stock=product.get("stock"),
                availability_status=product.get("availability_status"),
                shipping_information=product.get("shipping_information"),
                return_policy=product.get("return_policy"),
                warranty_information=product.get("warranty_information"),
                sku=product.get("sku"),
                dimensions=product.get("dimensions"),
                weight=product.get("weight"),
                minimum_order_quantity=product.get("minimum_order_quantity"),
            )
        )
    return ProductDetails(items=items).model_dump()


@tool
def get_product_reviews(
    product_name: str | None = None, product_id: int | None = None
) -> dict:
    """Retrieve customer feedback, ratings, and sentiment for a product.

    Use this when the user asks "What do people think about this?", "Show me reviews for product kiwi", or "Is this product any good?".
    If only a product name is provided, the tool will look up the product ID first.
    """
    if product_id is None:
        if not product_name:
            return ErrorResponse(
                message="Please provide a product name or product ID to fetch reviews."
            ).model_dump()

        products = get_products_by_title(product_name, limit=1)
        if not products:
            products = search_products_hybrid(product_name, limit=1)

        if not products:
            return ErrorResponse(
                message=f"No product found matching '{product_name}'."
            ).model_dump()

        product_id = products[0].get("id")
        if product_id is None:
            return ErrorResponse(
                message=f"Product '{product_name}' was found, but its ID is missing."
            ).model_dump()

    rows = _get_product_reviews(product_id, limit=5)
    if not rows:
        return ReviewResults(product_id=product_id, items=[]).model_dump()
    items = []
    for r in rows:
        items.append(
            ReviewItem(
                comment=r.get("comment"),
            )
        )

    summary = _summarize_reviews([i.comment for i in items if i.comment])
    return ReviewResponse(summary=summary).model_dump()


def _summarize_reviews(comments: list[str]) -> str | None:
    if not comments:
        return None

    llm = get_llm()
    system_prompt = (
        "You summarize customer review comments. "
        "Write 2-3 concise sentences about overall review summary of the product. "
        "Use only the provided comments. No bullets."
    )
    human_prompt = "Reviews:\n" + "\n".join(f"- {c}" for c in comments)
    try:
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt),
            ]
        )
    except Exception:
        return None

    content = getattr(response, "content", None)
    if not content:
        return None
    return str(content).strip()


@tool
def get_tag_categories() -> dict:
    """List the types of products, departments, or categories available in the store.

    Use this when the user asks "What products do you sell?", "What categories do you have?", "What types of items are available?", or "Show me the store departments".
    This is the best tool for an overview of the store's inventory structure and departments.
    """
    categories = list_tag_categories()
    if not categories:
        return CategoryList(items=[]).model_dump()
    return CategoryList(items=categories).model_dump()


@tool
def get_products_in_category(category: str) -> dict:
    """List all products belonging to a specific category or department name.

    Use this when the user wants to see everything in a section (e.g., "Show me all beauty products", "What items are in the groceries category?").
    The user must provide a valid category name.
    """
    products = get_products_by_category(category, limit=30)
    if not products:
        return CategoryProducts(category=category, items=[]).model_dump()
    items = []
    for p in products:
        items.append({"title": p.get("title"), "stock": p.get("stock")})
    return {"category": category, "items": items}


TOOLS = [
    get_product_by_name,
    get_product_reviews,
    get_tag_categories,
    get_products_in_category,
]
