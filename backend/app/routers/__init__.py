"""API routers."""

from .health import router as health_router
from .players import router as players_router
from .signals import router as signals_router
from .trades import router as trades_router
from .rankings import router as rankings_router
from .projections import router as projections_router
from .chat import router as chat_router
from .ml_monitor import router as ml_monitor_router
from .league import router as league_router

__all__ = [
    "health_router",
    "players_router",
    "signals_router",
    "trades_router",
    "rankings_router",
    "projections_router",
    "chat_router",
    "ml_monitor_router",
    "league_router",
]
