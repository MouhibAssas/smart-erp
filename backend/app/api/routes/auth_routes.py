from fastapi import APIRouter, Depends, Response, Request, HTTPException, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.services.auth_service import AuthService
from app.utils.token_utils import create_refresh_token, verify_refresh_token, create_access_token
from app.schemas.auth_schema import LoginRequest, TokenResponse
from app.schemas.user_schema import UserResponse
from app.middleware.dependencies import get_current_user
from app.models.user import User
from sqlalchemy.orm import Session
from app.database.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(response: Response, payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user, set refresh token cookie, and return access token."""
    service = AuthService(db)
    token_response = service.login(payload)

    # Create refresh token and set as httpOnly cookie scoped to the refresh endpoint
    # NOTE: secure=False for local development; set to True in production (HTTPS)
    # max_age corresponds to REFRESH_TOKEN_EXPIRE_DAYS (7 days)
    refresh_token = create_refresh_token(token_response.user.id)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/auth/refresh",
    )

    return token_response


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return current_user


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")

    user_id = verify_refresh_token(token)
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account not found or deactivated")

    # Issue fresh access token with current role from DB
    new_access_token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=new_access_token, token_type="bearer", user=UserResponse.model_validate(user))


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="refresh_token", path="/auth/refresh")
    return {"message": "Logged out"}
