from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from utils.dependencies import get_current_user, get_admin_user
from models import models, schemas
from crud import support_crud
from services.bot import bot


router = APIRouter()


@router.post("/", response_model=schemas.SupportRequestOut)
async def create_support_request(
    payload: schemas.SupportRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Создать обращение в поддержку.
    """
    request = await support_crud.create_support_request(
        db=db,
        user_id=current_user.id,
        summary=payload.summary,
        hub_id=payload.hub_id,
        badge_id=payload.badge_id,
        description=payload.description,
    )
    # создаём первое сообщение в треде
    await support_crud.add_support_message(
        db=db,
        request_id=request.id,
        sender_id=current_user.id,
        sender_is_admin=current_user.is_admin,
        body=payload.description,
    )
    return request


@router.get("/", response_model=list[schemas.SupportRequestOut])
async def list_support_requests(
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user),
):
    """
    Получить список всех обращений (только для администратора).
    """
    requests = await support_crud.list_support_requests(db)
    return requests


@router.get("/{request_id}/messages", response_model=list[schemas.SupportMessageOut])
async def get_support_thread(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Получить всю переписку по обращению (как тред в почте).
    Доступно владельцу обращения и администратору.
    """
    req = await support_crud.get_support_request(db, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Support request not found")
    if not (current_user.is_admin or req.user_id == current_user.id):
        raise HTTPException(status_code=403, detail="Not allowed to view this thread")

    messages = await support_crud.list_support_messages(db, request_id)
    return messages


@router.post("/{request_id}/messages", response_model=schemas.SupportMessageOut)
async def post_support_message(
    request_id: int,
    payload: schemas.SupportMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Добавить сообщение в тред обращения.
    Админ и пользователь используют один и тот же эндпоинт.
    """
    # проверяем, что текущий пользователь имеет право писать в этот тред
    req = await support_crud.get_support_request(db, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Support request not found")
    if not (current_user.is_admin or req.user_id == current_user.id):
        raise HTTPException(status_code=403, detail="Not allowed to post to this thread")

    message = await support_crud.add_support_message(
        db=db,
        request_id=request_id,
        sender_id=current_user.id,
        sender_is_admin=current_user.is_admin,
        body=payload.body,
    )
    # add_support_message уже проверяет существование, но мы это сделали выше

    # Если пишет админ — уведомляем пользователя в Telegram
    if message.sender_is_admin:
        if req and req.user and req.user.telegram_id:
            try:
                text = (
                    f"Новое сообщение по вашему обращению #{req.id} по хабу {req.hub_id}:\n"
                    f"{message.body}"
                )
                bot.send_message(req.user.telegram_id, text)
            except Exception:
                pass

    return message

