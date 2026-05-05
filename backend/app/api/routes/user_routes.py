from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.services.user_service import UserService
from app.schemas.user_schema import UserCreate, UserUpdate, UserResponse
from app.middleware.dependencies import require_roles
from app.services.conversation_service import ConversationService
from app.schemas.conversation_schema import ConversationResponse, ConversationDetailResponse, ConversationSearchResponse

router = APIRouter(prefix="/users", tags=["Users"], dependencies=[Depends(require_roles("admin"))])

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


# Admin: list conversations for a given user
@router.get("/{user_id}/conversations", response_model=List[ConversationResponse])
def admin_list_user_conversations(user_id: int, db: Session = Depends(get_db)):
    service = ConversationService(db)
    return service.get_user_conversations(user_id)


@router.get("/{user_id}/conversations/search", response_model=List[ConversationSearchResponse])
def admin_search_user_conversations(
    user_id: int,
    q: str = Query(default=""),
    db: Session = Depends(get_db),
):
    service = ConversationService(db)
    return service.search_user_conversations(user_id, q)


# Admin: get conversation detail for a given user
@router.get("/{user_id}/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def admin_get_user_conversation(user_id: int, conversation_id: int, db: Session = Depends(get_db)):
    service = ConversationService(db)
    return service.get_conversation(conversation_id, user_id)