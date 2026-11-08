
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Moko Management API",
        description="Management API for Moko",
        version="1.0.0"
    )

    # CORS - Allow requests from the Moko web dashboard
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Register API routes
    app.include_router(
        api_router,
        prefix="/api/v1",
    )

    return app


app = create_app()
