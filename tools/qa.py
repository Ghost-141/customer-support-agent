from langchain_core.tools import tool
from db import get_product_reviews as _get_product_reviews
from schemas import (
    ProductItem,
    ProductDetails,
    ReviewItem,
    ReviewResults,
    ErrorResponse,
    CategoryList,
    CategoryProducts,
    SearchResults,
)
from db import (
    search_products_hybrid,
    get_products_by_title,
    get_products_by_category,
    list_tag_categories,
)


@tool
def search_products(query: str) -> dict:
    """Find products by a natural-language query and return top matches.

    Use this when the user describes what they want (e.g., "smartwatch", "wireless earbuds").
    Input should be a short query string; the tool returns a list of ProductItem results
    with ids, titles, brands, categories, prices, ratings, and stock. If no matches are found,
    it returns an empty list.
    """
    if not query or not query.strip():
        return ErrorResponse(message="Missing query.").model_dump()
    rows = search_products_hybrid(query, limit=5)
    if not rows:
        return SearchResults(query=query.strip(), items=[]).model_dump()
    items = []
    for p in rows:
        items.append(
            ProductItem(
                title=p.get("title"),
                brand=p.get("brand"),
                category=p.get("category"),
                price=p.get("price"),
                stock=p.get("stock"),
            )
        )
    return SearchResults(query=query.strip(), items=items).model_dump()


@tool
def get_product_by_name(product_name: str) -> dict:
    """Fetch detailed product info by exact product title.

    Use this after you have a specific product name from the user or from search results.
    The input must match the product title (case-insensitive exact match).
    Returns a list of detailed product records; if nothing matches, returns an empty list.
    """
    products = get_products_by_title(product_name, limit=5)
    if not products:
        return ProductDetails(items=[]).model_dump()
    items = []
    for product in products:
        items.append(
            {
                "id": product.get("id"),
                "title": product.get("title"),
                "brand": product.get("brand"),
                "category": product.get("category"),
                "price": product.get("price"),
                "rating": product.get("rating"),
                "stock": product.get("stock"),
                "availability_status": product.get("availability_status"),
                "shipping_information": product.get("shipping_information"),
                "return_policy": product.get("return_policy"),
                "warranty_information": product.get("warranty_information"),
                "sku": product.get("sku"),
                "dimensions": product.get("dimensions"),
                "weight": product.get("weight"),
                "minimum_order_quantity": product.get("minimum_order_quantity"),
            }
        )
    return ProductDetails(items=items).model_dump()


@tool
def get_product_reviews(product_id: int) -> dict:
    """Get the most recent reviews for a product by numeric id.

    Use this after you have a product id from search or product details.
    Returns up to 5 reviews with rating, comment, reviewer name, and date.
    """

    rows = _get_product_reviews(product_id, limit=5)
    if not rows:
        return ReviewResults(product_id=product_id, items=[]).model_dump()
    items = []
    for r in rows:
        items.append(
            ReviewItem(
                rating=r.get("rating"),
                comment=r.get("comment"),
                reviewer_name=r.get("reviewer_name"),
                date=r.get("date"),
            )
        )
    return ReviewResults(product_id=product_id, items=items).model_dump()


@tool
def get_tag_categories() -> dict:
    """List all available product categories.

    Use this when the user asks what categories exist or wants to browse by category.
    Returns a list of category names; returns an empty list if none exist.
    """
    categories = list_tag_categories()
    if not categories:
        return CategoryList(items=[]).model_dump()
    return CategoryList(items=categories).model_dump()


@tool
def get_products_in_category(category: str) -> dict:
    """List products within a specific category.

    Use this when the user provides a category name (e.g., "beauty", "groceries").
    Returns a list of ProductItem entries for that category; empty if the category has no products.
    """
    products = get_products_by_category(category, limit=30)
    if not products:
        return CategoryProducts(category=category, items=[]).model_dump()
    items = []
    for p in products:
        # Return only essential fields to prevent token overflow
        items.append({"title": p.get("title"), "stock": p.get("stock")})
    return {"category": category, "items": items}


TOOLS = [
    search_products,
    get_product_by_name,
    get_product_reviews,
    get_tag_categories,
    get_products_in_category,
]
