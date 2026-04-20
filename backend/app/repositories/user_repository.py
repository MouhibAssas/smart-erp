from sqlalchemy.orm import Session
from typing import Optional, List
from app.repositories.base_repository import BaseRepository
from app.models.user import User

class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def email_exists(self, email: str) -> bool:
        return self.get_by_email(email) is not None

    def get_active_users(self) -> List[User]:
        return self.db.query(User).filter(User.is_active == True).all()

    def get_by_role(self, role: str) -> List[User]:
        return self.db.query(User).filter(User.role == role).all()

    def deactivate(self, user: User) -> User:
        user.is_active = False
        self.db.commit()
        self.db.refresh(user)
        return user