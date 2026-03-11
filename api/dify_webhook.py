from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from crud import support_crud
from models import schemas, models
from services.bot import bot


router = APIRouter()


@router.post("/ticket-reply", response_model=schemas.SupportMessageOut)
async def dify_ticket_reply(
    payload: schemas.DifyReply,
    db: AsyncSession = Depends(get_db),
):
    """
    Вебхук для Dify: ответ по тикету.

    Dify должно отправлять JSON с полями:
    - ticket_id: int — ID тикета в нашей системе
    - answer: str — ответ модели
    - status: Optional[str] — новый статус тикета (например, 'in_progress' или 'resolved')
    """
    req = await support_crud.get_support_request(db, payload.ticket_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Support request not found")

    # Обновляем статус, если пришёл
    if payload.status:
        req.status = payload.status
        await db.commit()
        await db.refresh(req)

    # Добавляем сообщение от ИИ как админское (sender_id=None)
    message = await support_crud.add_support_message(
        db=db,
        request_id=req.id,
        sender_id=0,
        sender_is_admin=True,
        body=payload.answer,
    )

    # Уведомляем пользователя в Telegram
    if req.user and req.user.telegram_id:
        try:
            text = (
                f"Новый ответ по вашему обращению #{req.id} по хабу {req.hub_id}:\n"
                f"{payload.answer}"
            )
            bot.send_message(req.user.telegram_id, text)
        except Exception:
            # Не роняем вебхук, если Telegram недоступен
            pass

    return message

