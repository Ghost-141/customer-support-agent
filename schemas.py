from typing_extensions import TypedDict
from typing import Annotated, List
from pydantic import BaseModel
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ChatbotState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


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


class ProductDetails(BaseModel):
    type: str = "product_details"
    items: list[dict]


class ReviewItem(BaseModel):
    rating: int | None = None
    comment: str | None = None
    reviewer_name: str | None = None
    date: str | None = None


class ReviewResults(BaseModel):
    type: str = "reviews"
    product_id: int
    items: list[ReviewItem]


class CategoryList(BaseModel):
    type: str = "categories"
    items: list[str]


class CategoryProducts(BaseModel):
    type: str = "category_products"
    category: str
    items: list[ProductItem]
