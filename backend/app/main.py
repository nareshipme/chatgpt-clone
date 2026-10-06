from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, conversations, health, me, messages, tenants
from app.config import settings
from app.llm.factory import validate_llm_config
from app.errors import NoStoreMiddleware, RequestIdMiddleware, register_error_handlers


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_llm_config()  # refuse to start with a missing key or the mock in production
    yield


app = FastAPI(title="Tessera Chat API", version="0.0.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(NoStoreMiddleware)
app.add_middleware(RequestIdMiddleware)
register_error_handlers(app)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(me.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
