from fastapi import Request
from psycopg_pool import AsyncConnectionPool


def get_db_pool(request: Request) -> AsyncConnectionPool:
    return request.app.state.db_pool
