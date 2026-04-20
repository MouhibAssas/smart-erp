from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.services.user_service import UserService
from app.schemas.user_schema import UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=UserResponse, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    return UserService(db).create_user(payload)

@router.get("/", response_model=List[UserResponse])
def list_users(db: Session = Depends(get_db)):
    return UserService(db).get_all_users()

@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return UserService(db).get_user(user_id)

@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    return UserService(db).update_user(user_id, payload)

@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    UserService(db).delete_user(user_id)

@router.patch("/{user_id}/toggle-active", response_model=UserResponse)
def toggle_active(user_id: int, db: Session = Depends(get_db)):
    return UserService(db).toggle_active(user_id)