"""Generic API response models."""

from datetime import datetime
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool = True
    data: T | None = None
    message: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response."""

    success: bool = True
    data: list[T] = []
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False
    data_updated_at: str | None = Field(
        None, description="ISO timestamp of when source data was last updated"
    )


class ErrorResponse(BaseModel):
    """Error response."""

    success: bool = False
    error: str
    detail: str | None = None
    code: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    database: str = "connected"
    node_count: int | None = None


class TierInfo(BaseModel):
    """User tier information."""

    tier: str = Field(..., description="FREE, PRO, or ELITE")
    trade_uses_today: int = 0
    trade_limit: int | None = None
    features: list[str] = []
