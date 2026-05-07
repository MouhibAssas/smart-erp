from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from app.database.session import get_db
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from app.config import settings
from app.models.user import User

security = HTTPBearer()


class Credentials(BaseModel):
    credentials: str


async def get_current_user(
    request_headers=Depends(security),
    db: Session = Depends(get_db)
):
    """Extract user from JWT access token in Authorization header and verify active status.

    Ensures the token has type "access" and that the user exists and is active.
    """
    token = request_headers.credentials

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        user_id = int(payload.get("sub"))
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Single indexed PK lookup to ensure account is active
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found or deactivated")

    token_role = payload.get("role")
    current_role = getattr(user.role, "value", user.role)
    if token_role != current_role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token role is stale",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
