from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


class AuthService:
    """Authentication service."""

    @staticmethod
    def create_user(db: Session, user_create: UserCreate) -> User:
        """Create a new user."""
        # Check if username exists
        if db.query(User).filter(User.username == user_create.username).first():
            raise ValueError("Username already exists")

        # Check if email exists
        if db.query(User).filter(User.email == user_create.email).first():
            raise ValueError("Email already exists")

        # Create new user
        hashed_password = get_password_hash(user_create.password)
        db_user = User(
            username=user_create.username, email=user_create.email, hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> User | None:
        """Authenticate a user."""
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User | None:
        """Get a user by ID."""
        return db.query(User).filter(User.id == user_id).first()
