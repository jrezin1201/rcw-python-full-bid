"""
API dependencies for FastAPI dependency injection.
Provides reusable dependencies for authentication and authorization.
"""

from typing import Annotated, Generator, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_session
from app.models.user import User
from app.schemas.token import TokenPayload
from app.services.user_service import UserService

logger = get_logger(__name__)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


def get_current_user(
    session: Annotated[Session, Depends(get_session)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.

    Args:
        session: Database session
        token: JWT access token

    Returns:
        Current user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            logger.warning("Token missing subject claim")
            raise credentials_exception
        token_data = TokenPayload(sub=int(user_id))
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise credentials_exception
    except ValueError:
        logger.warning("Invalid user ID in token")
        raise credentials_exception

    user = UserService.get_by_id(session, user_id=token_data.sub)  # type: ignore
    if user is None:
        logger.warning(f"User {token_data.sub} not found")
        raise credentials_exception
    if not user.is_active:
        logger.warning(f"Inactive user {user.id} attempted access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    return user


def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Dependency to ensure current user is active.

    Args:
        current_user: Current authenticated user

    Returns:
        Active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user


def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Dependency to ensure current user is an admin.

    Args:
        current_user: Current authenticated user

    Returns:
        Admin user

    Raises:
        HTTPException: If user is not an admin
    """
    if not UserService.is_admin(current_user):
        logger.warning(f"Non-admin user {current_user.id} attempted admin access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


def get_api_key(
    x_api_key: Optional[str] = Header(None)
) -> str:
    """
    Dependency to validate API key from X-API-Key header.

    Args:
        x_api_key: API key from header

    Returns:
        Validated API key

    Raises:
        HTTPException: If API key is invalid or missing
    """
    # Get the expected API key from settings
    expected_api_key = getattr(settings, 'API_KEY', None)

    # If no API key is configured, skip validation (for development)
    if not expected_api_key:
        logger.debug("API key validation skipped (not configured)")
        return "no-api-key-configured"

    # Check if API key was provided
    if not x_api_key:
        logger.warning("Missing API key in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Please provide X-API-Key header"
        )

    # Validate API key
    if x_api_key != expected_api_key:
        logger.warning(f"Invalid API key attempt: {x_api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    return x_api_key


def get_current_user_or_api_key(
    session: Annotated[Session, Depends(get_session)],
    token: Optional[str] = Depends(oauth2_scheme),
    x_api_key: Optional[str] = Header(None)
) -> Optional[User]:
    """
    Dependency that allows either JWT token or API key authentication.
    Returns the user if JWT token is provided, None if API key is used.

    Args:
        session: Database session
        token: Optional JWT access token
        x_api_key: Optional API key

    Returns:
        User object or None

    Raises:
        HTTPException: If neither valid token nor API key is provided
    """
    # Check for API key first
    if x_api_key:
        validated_key = get_api_key(x_api_key)
        if validated_key:
            return None  # API key auth doesn't have a user

    # Fall back to JWT token auth
    if token:
        return get_current_user(session, token)

    # Neither provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide either JWT token or X-API-Key header"
    )
