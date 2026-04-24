from langchain_core.tools import tool
from data.db import get_product_reviews as _get_product_reviews
from api.schemas import (
    ProductDetails,
    ProductDetailItem,
    ProductDisambiguation,
    ProductCandidateItem,
    ReviewItem,
    ReviewResults,
    ReviewResponse,
    CategoryList,
    CategoryProducts,
    ErrorResponse,
)
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from utils.llm_provider import get_llm
from data.db import (
    get_products_by_title,
    get_products_by_category,
    list_tag_categories,
    search_products_hybrid,
)


def _build_disambiguation(query: str, products: list[dict]) -> dict | None:
    unique = []
    seen_titles = set()

    for p in products:
        title = (p.get("title") or "").strip()
        if not title:
            continue
        title_key = title.lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        unique.append(
            ProductCandidateItem(
                id=p.get("id"),
                title=title,
                brand=p.get("brand"),
                category=p.get("category"),
                price=p.get("price"),
            )
        )

    if len(unique) <= 1:
        return None

    return ProductDisambiguation(
        query=query,
        message=(
            "I found multiple similar products. Please tell me which exact one you want."
        ),
        items=unique[:5],
    ).model_dump()


@tool
def get_product_by_name(product_name: str) -> dict:
    """Fetch technical specifications, current pricing, and real-time stock status for a SPECIFIC product.

    USE THIS TOOL WHEN:
    - The user provides a specific product name or title (e.g., "Red Nail Polish", "cat food", "kiwi").
    - The user asks about price, weight, dimensions, or availability of a known item.

    DO NOT USE THIS TOOL:
    - To browse categories or see lists of different products.
    - If the user is asking for 'reviews' or 'what people think' (use get_product_reviews instead).
    """
    # Try exact title match first
    products = get_products_by_title(product_name, limit=5)

    # If no exact match, fallback to hybrid search to be more helpful
    if not products:
        products = search_products_hybrid(product_name, limit=5)

    if not products:
        return ProductDetails(items=[]).model_dump()

    disambiguation = _build_disambiguation(product_name, products)
    if disambiguation:
        return disambiguation

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
    """Retrieve customer feedback, star ratings, and quality sentiment for a product.

    USE THIS TOOL WHEN:
    - The user asks for opinions, reviews, or "what people think" about an item.
    - The user asks "is this product any good?" or "show me feedback".

    DO NOT USE THIS TOOL:
    - To find out the price, stock status, or technical specs (use get_product_by_name instead).
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


class CategoryArgs(BaseModel):
    category: str = Field(
        ...,
        description="The exact category name to filter by (e.g., 'beauty', 'groceries', 'fragrances').",
    )


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
    """Get a high-level list of all available product departments and categories in the store.

    USE THIS TOOL WHEN:
    - The user asks "what do you sell?", "show me your categories", or "what departments do you have?".
    - The user wants an overview of the store's inventory structure.
    """
    categories = list_tag_categories()
    if not categories:
        return CategoryList(items=[]).model_dump()
    return CategoryList(items=categories).model_dump()


@tool(args_schema=CategoryArgs)
def get_products_in_category(category: str) -> dict:
    """List all individual products found within a specific category or department.

    USE THIS TOOL WHEN:
    - The user wants to see a list of items in a department (e.g., "show me all beauty products").
    - The user asks "what items are in [category]?".

    DO NOT USE THIS TOOL:
    - To get details on a specific product (use get_product_by_name instead).
    - If the user hasn't specified which category they are interested in.
    """
    if not isinstance(category, str) or not category.strip():
        return ErrorResponse(
            message="Please provide a single category name as a string."
        ).model_dump()
    category = category.strip()

    products = get_products_by_category(category, limit=30)
    if not products:
        return CategoryProducts(category=category, items=[]).model_dump()

    actual_category = products[0].get("category") or category
    items = []
    for p in products:
        items.append({"title": p.get("title"), "stock": p.get("stock")})
    return {"category": actual_category, "items": items}


TOOLS = [
    get_product_by_name,
    get_product_reviews,
    get_tag_categories,
    get_products_in_category,
]
