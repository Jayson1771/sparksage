from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import auth, config, providers, bot, conversations, wizard
import db
from api.routes.api_analytics_router import router as analytics_router
from api.routes.member_analytics_router import router as members_router
from api.routes.config import router as config_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    await db.sync_env_to_db()
    yield
    await db.close_db()


def create_app() -> FastAPI:
    app = FastAPI(title="SparkSage API", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(config.router, prefix="/api/config", tags=["config"])
    app.include_router(providers.router, prefix="/api/providers", tags=["providers"])
    app.include_router(bot.router, prefix="/api/bot", tags=["bot"])
    app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
    app.include_router(analytics_router)
    app.include_router(wizard.router, prefix="/api/wizard", tags=["wizard"])
    app.include_router(members_router)
    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app
