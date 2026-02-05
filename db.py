import os
from typing import Any, Dict, List

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
import json


load_dotenv()
load_dotenv(".env.example", override=False)


def _build_db_url() -> str:
    url = os.getenv("SUPASEBASE_DB_URL")
    if url:
        return url
    host = os.getenv("SUPASEBASE_DB_HOST")
    name = os.getenv("SUPASEBASE_DB_NAME")
    user = os.getenv("SUPASEBASE_DB_USER")
    password = os.getenv("SUPASEBASE_DB_PASSWORD")
    port = os.getenv("SUPASEBASE_DB_PORT")
    if not all([host, name, user, password, port]):
        raise RuntimeError(
            "Missing DB settings. Set SUPASEBASE_DB_URL or the SUPASEBASE_DB_* parts."
        )
    return f"postgresql://{user}:{password}@{host}:{port}/{name}?sslmode=require"


DB_URL = _build_db_url()


def _connect():
    return psycopg.connect(DB_URL, row_factory=dict_row)


def search_products_hybrid(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    if not query or not query.strip():
        return []
    query_clean = query.strip()
    q = f"%{query_clean}%"
    sql = """
    select
      p.title,
      p.brand,
      p.category,
      p.price,
      p.stock,
      (p.title ilike %(q_exact)s) as exact_title_match,
      ts_rank_cd(
        to_tsvector(
          'english',
          coalesce(p.title, '') || ' ' ||
          coalesce(p.category, '') || ' ' ||
          coalesce(p.brand, '') || ' ' ||
        ),
        websearch_to_tsquery('english', %(q_ts)s)
      ) as keyword_rank,
      (
        p.title ilike %(q)s
        or p.category ilike %(q)s
        or p.brand ilike %(q)s
      ) as keyword_match
    from products p
    order by
      exact_title_match desc,
      keyword_rank desc,
      keyword_match desc
    limit %(limit)s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "q": q,
                    "q_exact": query_clean,
                    "q_ts": query_clean,
                    "limit": limit,
                },
            )
            return cur.fetchall()


def get_product_by_id(product_id: int) -> Dict[str, Any] | None:
    sql = """
    select *
    from products
    where id = %(id)s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"id": product_id})
            return cur.fetchone()


def get_products_by_title(title: str, limit: int = 5) -> List[Dict[str, Any]]:
    sql = """
    select *
    from products
    where lower(title) = lower(%(title)s)
    limit %(limit)s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"title": title, "limit": limit})
            return cur.fetchall()


def get_products_by_category(category: str, limit: int = 5) -> List[Dict[str, Any]]:
    sql = """
    select title, price, stock
    from products
    where lower(category) = lower(%(category)s)
    order by title
    limit %(limit)s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"category": category, "limit": limit})
            return cur.fetchall()


def get_product_reviews(product_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    sql = """
    select rating, comment, date, reviewer_name, reviewer_email
    from product_reviews
    where product_id = %(id)s
    order by date desc nulls last
    limit %(limit)s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"id": product_id, "limit": limit})
            return cur.fetchall()


def list_tag_categories() -> List[str]:
    sql = """
    select distinct category
    from products
    where category is not null
    order by category
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return [row["category"] for row in rows if row.get("category")]


def init_db():
    """Initializes the database schema."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS product_reviews;")
            cur.execute("DROP TABLE IF EXISTS products;")

            cur.execute(
                """
                CREATE TABLE products (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    description TEXT,
                    category TEXT,
                    price NUMERIC,
                    discount_percentage NUMERIC,
                    rating NUMERIC,
                    stock INTEGER,
                    brand TEXT,
                    sku TEXT,
                    weight INTEGER,
                    dimensions JSONB,
                    warranty_information TEXT,
                    shipping_information TEXT,
                    availability_status TEXT,
                    return_policy TEXT,
                    minimum_order_quantity INTEGER,
                    meta JSONB,
                    thumbnail TEXT
                );
            """
            )
            cur.execute(
                """
                CREATE TABLE product_reviews (
                    product_id INTEGER REFERENCES products(id),
                    rating INTEGER,
                    comment TEXT,
                    date TEXT,
                    reviewer_name TEXT,
                    reviewer_email TEXT
                );
            """
            )


def seed_db():
    """Seeds the database with data from products.json."""
    with open("products.json", "r") as f:
        data = json.load(f)

    with _connect() as conn:
        with conn.cursor() as cur:
            for p in data["products"]:
                cur.execute(
                    """
                    INSERT INTO products (
                        id, title, description, category, price, discount_percentage, rating, stock,
                        brand, sku, weight, dimensions, warranty_information, shipping_information,
                        availability_status, return_policy, minimum_order_quantity, meta, thumbnail
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        p["id"],
                        p["title"],
                        p["description"],
                        p["category"],
                        p["price"],
                        p.get("discountPercentage"),
                        p["rating"],
                        p["stock"],
                        p.get("brand"),
                        p.get("sku"),
                        p.get("weight"),
                        json.dumps(p.get("dimensions")),
                        p.get("warrantyInformation"),
                        p.get("shippingInformation"),
                        p.get("availabilityStatus"),
                        p.get("returnPolicy"),
                        p.get("minimumOrderQuantity"),
                        json.dumps(p.get("meta")),
                        p.get("thumbnail"),
                    ),
                )

                for r in p.get("reviews", []):
                    cur.execute(
                        "INSERT INTO product_reviews (product_id, rating, comment, date, reviewer_name, reviewer_email) VALUES (%s, %s, %s, %s, %s, %s)",
                        (
                            p["id"],
                            r["rating"],
                            r["comment"],
                            r["date"],
                            r["reviewerName"],
                            r["reviewerEmail"],
                        ),
                    )


if __name__ == "__main__":
    init_db()
    seed_db()
    print("Database seeded successfully.")
