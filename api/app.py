from contextlib import asynccontextmanager
from fastapi import FastAPI
from db_pool import create_async_pool
from api.routers.whatsapp import whatsapp_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = create_async_pool()
    await pool.open()
    app.state.db_pool = pool
    try:
        yield
    finally:
        await pool.close()


app = FastAPI(lifespan=lifespan)
app.include_router(whatsapp_router, tags=["whatsapp"])
