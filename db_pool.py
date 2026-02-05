from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

from db import _build_db_url


def create_async_pool() -> AsyncConnectionPool:
    conn_info = _build_db_url()
    return AsyncConnectionPool(
        conninfo=conn_info,
        max_size=20,
        kwargs={
            "autocommit": True,
            "prepare_threshold": None,
            "row_factory": dict_row,
        },
    )
