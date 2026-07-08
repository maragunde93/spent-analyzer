import asyncio
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth, cash, dashboard, expenses, fx, history, households, imports, receipts
from app.config import get_settings, should_seed_development_data, validate_production_settings
from app.database import Base, SessionLocal, engine, init_db
from app.dev_seed import seed_development_data
from app.services.fx_updater import run_daily_blue_rate_update


def create_app() -> FastAPI:
    settings = get_settings()
    validate_production_settings(settings)
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie=settings.session_cookie_name,
        path=settings.session_cookie_path,
        same_site=settings.session_cookie_samesite,
        https_only=settings.session_cookie_secure,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(households.router)
    app.include_router(expenses.router)
    app.include_router(dashboard.router)
    app.include_router(imports.router)
    app.include_router(cash.router)
    app.include_router(fx.router)
    app.include_router(history.router)
    app.include_router(receipts.router)

    @app.on_event("startup")
    async def startup() -> None:
        init_db()
        if should_seed_development_data(settings):
            with SessionLocal() as db:
                seed_development_data(db)
        if settings.fx_auto_update_enabled:
            app.state.fx_update_task = asyncio.create_task(
                run_daily_blue_rate_update(
                    SessionLocal,
                    api_url=settings.fx_api_url,
                    hour_argentina=settings.fx_update_hour_argentina,
                )
            )

    @app.on_event("shutdown")
    async def shutdown() -> None:
        task = getattr(app.state, "fx_update_task", None)
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    if settings.test_auth_enabled:
        @app.post("/test/reset")
        def reset_test_database() -> dict:
            Base.metadata.drop_all(bind=engine)
            init_db()
            with SessionLocal() as db:
                seed_development_data(db)
            return {"ok": True}

    return app


app = create_app()
