from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.schemas.user_schema import UserCreate, UserUpdate
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

class UserService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def create_user(self, data: UserCreate) -> User:
        if self.repo.email_exists(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email '{data.email}' is already registered"
            )
        user = User(
            full_name=data.full_name,
            email=data.email,
            hashed_password=hash_password(data.password),
            role=data.role
        )
        return self.repo.save(user)

    def get_user(self, user_id: int) -> User:
        user = self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    def get_all_users(self) -> list[User]:
        return self.repo.get_all()

    def update_user(self, user_id: int, data: UserUpdate) -> User:
        user = self.get_user(user_id)
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.email is not None:
            if self.repo.email_exists(data.email):
                raise HTTPException(status_code=409, detail="Email already in use")
            user.email = data.email
        if data.role is not None:
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active
        self.repo.db.commit()
        self.repo.db.refresh(user)
        return user

    def delete_user(self, user_id: int) -> None:
        user = self.get_user(user_id)
        self.repo.delete(user)
        
    def toggle_active(self, user_id: int) -> User:
        user = self.get_user(user_id)
        user.is_active = not user.is_active
        self.repo.db.commit()
        self.repo.db.refresh(user)
        return user