from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from app.database.session import get_db
from app.services.auth_service import AuthService
from app.utils.token_utils import decode_access_token
from sqlalchemy.orm import Session

security = HTTPBearer()


class Credentials(BaseModel):
    credentials: str


async def get_current_user(
    request_headers=Depends(security),
    db: Session = Depends(get_db)
):
    """Extract user from JWT token in Authorization header."""
    token = request_headers.credentials
    
    # Decode token
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_id = int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    auth_service = AuthService(db)
    user = auth_service.get_user_from_token(user_id)
    
    return user


def require_roles(*allowed_roles):
    """Create a role-based dependency checker for protected routes."""

    def role_checker(current_user=Depends(get_current_user)):
        role = getattr(current_user, "role", None)
        role_value = getattr(role, "value", role)

        if role_value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return current_user

    return role_checker
