from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import projects


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AplicAI API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_base_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(projects.router)
    return app


app = create_app()
