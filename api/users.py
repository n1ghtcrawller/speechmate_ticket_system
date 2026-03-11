from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from utils.dependencies import get_current_user
from services.users_service import UserService
from models import schemas, models
from logger import get_api_logger

logger = get_api_logger("users")

router = APIRouter()

@router.get("/me", response_model=schemas.UserOut)
async def read_me(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получение профиля текущего пользователя"""
    user = await UserService.get_user_profile(db, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/me", response_model=schemas.UserOut)
async def update_me(
        payload: schemas.ProfileUpdate = Body(...),
        # <-- явно указываем, что тело обязательно, но поля внутри опциональны
        db: AsyncSession = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """Обновление профиля текущего пользователя"""
    updates = payload.dict(exclude_unset=True)
    user = await UserService.update_user_profile(db, current_user, updates)
    return user
