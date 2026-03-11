from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, Any
import json
import os

from models import models
from crud import users_crud
from logger import get_api_logger


logger = get_api_logger("users_services")


class UserService:
    """Сервис для работы с пользователями"""
    
    @staticmethod
    async def authenticate_telegram_user(
        db: AsyncSession, 
        init_data: str, 
        ref_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Аутентификация пользователя через Telegram Web App

        Args:
            db: Сессия базы данных
            init_data: Данные инициализации от Telegram
            ref_code: Реферальный код (опционально)

        Returns:
            Dict с данными пользователя и токеном
        """
        from utils.telegram_auth import check_telegram_webapp_auth
        from config import settings
        from utils.jwt import create_access_token
        
        # Проверяем подпись Telegram
        data = check_telegram_webapp_auth(init_data, bot_token=settings.BOT_TOKEN.strip())
        if not data:
            raise ValueError("Invalid Telegram auth data")

        # Если ref_code не пришёл в body → достаём из start_param
        if not ref_code:
            start_param = data.get("start_param")
            if start_param and start_param.startswith("ref_"):
                ref_code = start_param.replace("ref_", "")

        user_json = data.get("user")
        if not user_json:
            raise ValueError("User data missing in Telegram auth data")
        
        user_data = json.loads(user_json)
        telegram_id = int(user_data.get("id"))

        # Проверяем, есть ли пользователь
        user = await users_crud.get_user_by_telegram(db, telegram_id)
        is_new = False

        if not user:
            # Ищем id пригласившего по ref_code
            inviter_id = None
            if ref_code:
                inviter_result = await db.execute(select(models.User).filter(models.User.ref_code == ref_code))
                inviter = inviter_result.scalar_one_or_none()
                if inviter:
                    inviter_id = inviter.id

            # Создаём нового пользователя
            user = await users_crud.create_user_from_telegram(db, user_data, invited_by=inviter_id)
            is_new = True
            logger.info(f"New user created: {user.id}")

        # Обновляем флаг администратора на основе переменной окружения ADMIN
        admin_telegram_id = os.getenv("ADMIN")
        if admin_telegram_id is not None and telegram_id == int(admin_telegram_id):
            if not user.is_admin:
                user.is_admin = True
                await db.commit()
                await db.refresh(user)

        # Генерируем токен
        token = create_access_token({"sub": str(user.id)})
        
        logger.info(f"User authenticated: {user.id}, is_new: {is_new}")
        
        return {
            "user": user,
            "access_token": token,
            "token_type": "bearer",
            "is_new": is_new
        }

    @staticmethod
    async def get_user_profile(db: AsyncSession, user_id: int) -> Optional[models.User]:
        """
        Получение профиля пользователя по ID
        
        Args:
            db: Сессия базы данных
            user_id: ID пользователя
            
        Returns:
            Объект пользователя или None
        """
        user = await users_crud.get_user(db, user_id)
        if user:
            logger.info(f"User profile retrieved: {user_id}")
        else:
            logger.warning(f"User not found: {user_id}")
        return user

    @staticmethod
    async def update_user_profile(
        db: AsyncSession, 
        user: models.User, 
        updates: Dict[str, Any]
    ) -> models.User:
        """
        Обновление профиля пользователя
        
        Args:
            db: Сессия базы данных
            user: Объект пользователя
            updates: Словарь с обновлениями
            
        Returns:
            Обновленный объект пользователя
        """
        try:
            updated_user = await users_crud.update_profile(db, user, updates)
            logger.info(f"User profile updated: {user.id}, updates: {list(updates.keys())}")
            return updated_user
        except Exception as e:
            logger.error(f"Failed to update user profile {user.id}: {str(e)}")
            raise

    @staticmethod
    async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> Optional[models.User]:
        """
        Получение пользователя по Telegram ID
        
        Args:
            db: Сессия базы данных
            telegram_id: Telegram ID пользователя
            
        Returns:
            Объект пользователя или None
        """
        user = await users_crud.get_user_by_telegram(db, telegram_id)
        if user:
            logger.info(f"User found by telegram_id: {telegram_id}")
        else:
            logger.warning(f"User not found by telegram_id: {telegram_id}")
        return user

    @staticmethod
    async def create_user_from_telegram_data(
        db: AsyncSession, 
        user_data: Dict[str, Any], 
        invited_by: Optional[int] = None
    ) -> models.User:
        """
        Создание нового пользователя из данных Telegram
        
        Args:
            db: Сессия базы данных
            user_data: Данные пользователя от Telegram
            invited_by: ID пригласившего пользователя
            
        Returns:
            Созданный объект пользователя
        """
        try:
            user = await users_crud.create_user_from_telegram(db, user_data, invited_by)
            logger.info(f"User created from telegram data: {user.id}")
            return user
        except Exception as e:
            logger.error(f"Failed to create user from telegram data: {str(e)}")
            raise
