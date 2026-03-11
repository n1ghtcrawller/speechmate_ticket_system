from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import models
from datetime import datetime
from logger import get_crud_logger

logger = get_crud_logger("users_crud")


async def get_user_by_telegram(db: AsyncSession, telegram_id: int):
    result = await db.execute(select(models.User).filter(models.User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_user(db: AsyncSession, user_id: int):
    result = await db.execute(select(models.User).filter(models.User.id == user_id))
    return result.scalar_one_or_none()


async def create_user_from_telegram(db: AsyncSession, data: dict, invited_by: int = None):
    user = models.User(
        telegram_id=int(data.get("id")),
        username=data.get("username"),
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        invited_by=invited_by
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    balance = models.UserBalance(
        user_id=user.id,
        balance=0
    )
    db.add(balance)
    await db.commit()
    await db.refresh(balance)

    return user


async def update_profile(db: AsyncSession, user: models.User, updates: dict):
    try:
        for k, v in updates.items():
            if hasattr(user, k) and v is not None:
                setattr(user, k, v)
        await db.commit()
        await db.refresh(user)
        return user
    except Exception as e:
        print(e)
