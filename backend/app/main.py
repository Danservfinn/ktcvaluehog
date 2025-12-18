"""Dynasty Edge API - FastAPI Application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import (
    health_router,
    players_router,
    signals_router,
    trades_router,
    rankings_router,
    projections_router,
    chat_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    settings = get_settings()
    print(f"Starting {settings.app_name} v{settings.app_version}")
    yield
    # Shutdown
    print("Shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
Dynasty Edge API - Fantasy football dynasty analysis powered by Neo4j graph database and ML.

## Features
- **Player Search & Profiles**: Search 25K+ NFL players with filtering
- **Edge Signals**: ML-powered buy/sell recommendations (R² = 0.87)
- **Trade Analyzer**: Evaluate trades with KTC values and predictions
- **Production Leaders**: 2025 season stats and rankings

## Tiers
- **Free**: 100 rankings, 3 trades/day
- **Pro ($9.99/mo)**: 500 rankings, unlimited trades
- **Elite ($19.99/mo)**: All features + ML projections + Thoth AI

## Authentication
Supabase JWT tokens required for authenticated endpoints.
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(players_router, prefix="/api/v1")
    app.include_router(signals_router, prefix="/api/v1")
    app.include_router(trades_router, prefix="/api/v1")
    app.include_router(rankings_router, prefix="/api/v1")
    app.include_router(projections_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


# Application instance
app = create_app()
