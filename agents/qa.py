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
    """Search the product catalog by user query and return top matches with ids."""
    if not query or not query.strip():
        return ErrorResponse(message="Missing query.").model_dump()
    rows = search_products_hybrid(query, limit=5)
    if not rows:
        return SearchResults(query=query.strip(), items=[]).model_dump()
    items = []
    for p in rows:
        items.append(
            ProductItem(
                id=p.get("id"),
                title=p.get("title"),
                brand=p.get("brand"),
                category=p.get("category"),
                price=p.get("price"),
                rating=p.get("avg_rating"),
                stock=p.get("stock"),
            )
        )
    return SearchResults(query=query.strip(), items=items).model_dump()


@tool
def get_product_by_name(product_name: str) -> dict:
    """Fetch full product details by exact product name/title."""
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
            }
        )
    return ProductDetails(items=items).model_dump()


@tool
def get_product_reviews(product_id: int) -> dict:
    """Fetch recent reviews for a product by its numeric id."""

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
    """List available product categories from the products table."""
    categories = list_tag_categories()
    if not categories:
        return CategoryList(items=[]).model_dump()
    return CategoryList(items=categories).model_dump()


@tool
def get_products_in_category(category: str) -> dict:
    """List products for a specific category from the products table."""
    products = get_products_by_category(category, limit=10)
    if not products:
        return CategoryProducts(category=category, items=[]).model_dump()
    items = []
    for p in products:
        items.append(
            ProductItem(
                id=p.get("id"),
                title=p.get("title"),
                category=p.get("category"),
                price=p.get("price"),
                rating=p.get("rating"),
                stock=p.get("stock"),
            )
        )
    return CategoryProducts(category=category, items=items).model_dump()


TOOLS = [
    search_products,
    get_product_by_name,
    get_product_reviews,
    get_tag_categories,
    get_products_in_category,
]
