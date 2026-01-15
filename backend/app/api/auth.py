from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.database import get_db
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
async def register(user_create: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    try:
        user = AuthService.create_user(db, user_create)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/login", response_model=Token)
async def login(user_login: UserLogin, db: Session = Depends(get_db)):
    """Login a user."""
    user = AuthService.authenticate_user(db, user_login.username, user_login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    response = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # 开发环境用 False，生产环境应设为 True
        samesite="lax",
        max_age=30 * 24 * 60 * 60,  # 30 天（秒）
    )
    return response


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return current_user


@router.post("/logout")
async def logout():
    """Logout a user by clearing the authentication cookie."""
    response = JSONResponse(content={"message": "Successfully logged out"})
    response.delete_cookie("access_token")
    return response
