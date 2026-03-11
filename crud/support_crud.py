from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import models
from logger import get_crud_logger


logger = get_crud_logger("support_crud")


async def create_support_request(
    db: AsyncSession,
    user_id: int,
    summary: str,
    hub_id: str,
    badge_id: Optional[str],
    description: str,
    status: str = "open",
) -> models.SupportRequest:
    request = models.SupportRequest(
        user_id=user_id,
        summary=summary,
        hub_id=hub_id,
        badge_id=badge_id,
        description=description,
        status=status,
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)

    logger.info(f"Support request created: id={request.id}, user_id={user_id}, hub_id={hub_id}")
    return request


async def list_support_requests(db: AsyncSession) -> List[models.SupportRequest]:
    result = await db.execute(select(models.SupportRequest).order_by(models.SupportRequest.date.desc()))
    return result.scalars().all()


async def get_support_request(db: AsyncSession, request_id: int) -> models.SupportRequest | None:
    result = await db.execute(
        select(models.SupportRequest).filter(models.SupportRequest.id == request_id)
    )
    return result.scalar_one_or_none()


async def add_support_message(
    db: AsyncSession,
    request_id: int,
    sender_id: int,
    sender_is_admin: bool,
    body: str,
) -> models.SupportMessage | None:
    result = await db.execute(
        select(models.SupportRequest).filter(models.SupportRequest.id == request_id)
    )
    request = result.scalar_one_or_none()
    if request is None:
        return None

    message = models.SupportMessage(
        request_id=request_id,
        sender_id=sender_id,
        sender_is_admin=sender_is_admin,
        body=body,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    logger.info(
        f"Support message added: request_id={request_id}, sender_id={sender_id}, is_admin={sender_is_admin}"
    )
    return message


async def list_support_messages(db: AsyncSession, request_id: int) -> List[models.SupportMessage]:
    result = await db.execute(
        select(models.SupportMessage)
        .filter(models.SupportMessage.request_id == request_id)
        .order_by(models.SupportMessage.created_at.asc())
    )
    return result.scalars().all()

