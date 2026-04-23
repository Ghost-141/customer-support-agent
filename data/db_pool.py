from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from data.db import _build_db_url


def create_async_pool() -> AsyncConnectionPool:
    conn_info = _build_db_url()
    return AsyncConnectionPool(
        conninfo=conn_info,
        open=False,
        min_size=1,  # Keep at least one connection alive
        max_size=20,
        max_idle=300, # Close connections that are idle for more than 5 minutes
        check=AsyncConnectionPool.check_connection, # Check connection health on checkout
        kwargs={
            "autocommit": True,
            "prepare_threshold": None,
            "row_factory": dict_row,
        },
    )
