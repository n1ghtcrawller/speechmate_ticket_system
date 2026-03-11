from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from models import schemas
from services.users_service import UserService


router = APIRouter()


@router.post("/telegram-login", response_model=schemas.Token)
async def telegram_login(request: schemas.TelegramLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Логин через Telegram Web App.
    Если передан ref_code, новый пользователь получает invited_by.
    """
    try:
        result = await UserService.authenticate_telegram_user(
            db=db,
            init_data=request.init_data,
            ref_code=request.ref_code
        )
        
        return {
            "access_token": result["access_token"],
            "token_type": result["token_type"],
            "is_new": result["is_new"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")