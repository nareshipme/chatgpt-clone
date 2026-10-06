from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, conversations, health, me, messages
from app.config import settings
from app.errors import NoStoreMiddleware, RequestIdMiddleware, register_error_handlers

app = FastAPI(title="Tessera Chat API", version="0.0.1")

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
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
