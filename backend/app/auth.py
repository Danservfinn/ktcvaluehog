"""Supabase JWT authentication middleware."""

from typing import Optional
from fastapi import Depends, HTTPException, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel
from enum import Enum

from .config import get_settings


class UserTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ELITE = "elite"


class User(BaseModel):
    """Authenticated user from Supabase JWT."""
    id: str
    email: str
    tier: UserTier = UserTier.FREE
    trade_uses_today: int = 0


# Security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[User]:
    """
    Extract and validate user from Supabase JWT.
    Returns None for anonymous users (allowed for free tier endpoints).
    """
    if not credentials:
        return None

    settings = get_settings()

    if not settings.supabase_jwt_secret:
        # Auth not configured - allow all requests (dev mode)
        return None

    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )

        # Extract user info from Supabase JWT
        user_id = payload.get("sub")
        email = payload.get("email", "")

        # Get tier from app_metadata (set via Supabase dashboard or webhook)
        app_metadata = payload.get("app_metadata", {})
        tier_str = app_metadata.get("tier", "free")
        tier = UserTier(tier_str) if tier_str in [t.value for t in UserTier] else UserTier.FREE

        return User(
            id=user_id,
            email=email,
            tier=tier,
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


async def require_auth(
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """Require authenticated user. Raises 401 if not authenticated."""
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_pro(
    user: User = Depends(require_auth),
) -> User:
    """Require Pro or Elite tier."""
    if user.tier == UserTier.FREE:
        raise HTTPException(
            status_code=403,
            detail="Pro subscription required for this feature",
        )
    return user


async def require_elite(
    user: User = Depends(require_auth),
) -> User:
    """Require Elite tier."""
    if user.tier != UserTier.ELITE:
        raise HTTPException(
            status_code=403,
            detail="Elite subscription required for this feature",
        )
    return user


def get_tier_limit(user: Optional[User], free_limit: int, pro_limit: int, elite_limit: int) -> int:
    """Get appropriate limit based on user tier."""
    if not user:
        return free_limit

    if user.tier == UserTier.ELITE:
        return elite_limit
    elif user.tier == UserTier.PRO:
        return pro_limit
    else:
        return free_limit


# BYOK (Bring Your Own Key) - for Claude AI chat
async def get_anthropic_key(
    x_anthropic_key: Optional[str] = Header(None, alias="X-Anthropic-Key"),
    user: User = Depends(require_elite),
) -> str:
    """
    Get Anthropic API key from header (BYOK pattern).
    Requires Elite tier.
    """
    if not x_anthropic_key:
        raise HTTPException(
            status_code=400,
            detail="X-Anthropic-Key header required for AI features. Add your API key in Settings.",
        )

    # Basic validation
    if not x_anthropic_key.startswith("sk-ant-"):
        raise HTTPException(
            status_code=400,
            detail="Invalid Anthropic API key format",
        )

    return x_anthropic_key
