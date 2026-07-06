from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, cash, dashboard, expenses, fx, history, households, imports, receipts
from app.config import get_settings
from app.database import Base, SessionLocal, engine, init_db
from app.dev_seed import seed_development_data


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
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
    def startup() -> None:
        init_db()
        with SessionLocal() as db:
            seed_development_data(db)

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
