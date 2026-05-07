from typing import Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.config import settings
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService, verify_password
from app.schemas.auth_schema import LoginRequest, TokenResponse
from app.schemas.user_schema import UserResponse
from app.utils.token_utils import create_access_token


class AuthService:
    def __init__(self, db: Session):
        self.user_service = UserService(db)
        self.user_repo = UserRepository(db)

    def login(self, data: LoginRequest) -> TokenResponse:
        """Authenticate user and return an access token and user payload.

        Note: the refresh token is set by the route handler as an httpOnly cookie.
        """
        # Find user by email
        user = self.user_repo.get_by_email(data.email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Verify password
        if not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive",
            )

        # Generate access token (include sub and role)
        token = create_access_token({"sub": str(user.id), "role": user.role})

        return TokenResponse(access_token=token, user=UserResponse.model_validate(user))

    def get_user_from_token(self, user_id: int) -> Any:
        """Get user object from user_id (extracted from token)."""
        return self.user_service.get_user(user_id)
