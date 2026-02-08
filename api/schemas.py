from typing_extensions import TypedDict
from typing import Annotated, List
from pydantic import BaseModel
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ChatbotState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    summary: str | None
    retrieved_tools: List[str]


class ErrorResponse(BaseModel):
    type: str = "error"
    message: str


class ProductItem(BaseModel):
    title: str | None
    brand: str | None = None
    category: str | None = None
    price: float | None = None
    stock: int | None = None


class SearchResults(BaseModel):
    type: str = "search_results"
    query: str
    items: list[ProductItem]


class ProductDetailItem(BaseModel):
    id: int | None = None
    title: str | None = None
    brand: str | None = None
    category: str | None = None
    price: float | None = None
    rating: float | None = None
    stock: int | None = None
    availability_status: str | None = None
    shipping_information: str | None = None
    return_policy: str | None = None
    warranty_information: str | None = None
    sku: str | None = None
    dimensions: dict | None = None
    weight: int | None = None
    minimum_order_quantity: int | None = None


class ProductDetails(BaseModel):
    type: str = "product_details"
    items: list[ProductDetailItem]


class ReviewItem(BaseModel):
    comment: str | None = None


class ReviewResults(BaseModel):
    type: str = "reviews"
    product_id: int
    items: list[ReviewItem]


class ReviewResponse(BaseModel):
    summary: str | None = None


class CategoryList(BaseModel):
    type: str = "categories"
    items: list[str]


class CategoryProducts(BaseModel):
    type: str = "category_products"
    category: str
    items: list[ProductItem]
