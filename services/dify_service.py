import logging
from typing import List

import httpx

from config import settings
from models import models
from crud import support_crud
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


def _build_workflow_url() -> str:
    """
    Построение URL вида:
    {DIFY_BASE_URL}/v1/workflows/run

    Для запуска конкретного workflow Dify использует связку API-ключа и приложения,
    так что ID в path не обязателен.
    """
    base = settings.DIFY_BASE_URL.rstrip("/")
    return f"{base}/v1/workflows/run"


async def _run_dify_workflow(inputs: dict, user_identifier: str) -> None:
    """
    Запуск воркфлоу Dify по официальной документации.
    """
    if not settings.DIFY_API_KEY:
        logger.warning("DIFY_API_KEY is not set; skipping Dify call.")
        return

    url = _build_workflow_url()

    payload = {
        "inputs": inputs,
        "response_mode": settings.DIFY_RESPONSE_MODE,
        "user": user_identifier,
    }

    headers = {
        "Authorization": f"Bearer {settings.DIFY_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.error(f"Dify workflow error: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Failed to call Dify workflow: {e}")


def _serialize_user(user: models.User) -> dict:
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_admin": getattr(user, "is_admin", False),
        "verified_status": getattr(user, "verified_status", None),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _serialize_message(msg: models.SupportMessage) -> dict:
    return {
        "id": msg.id,
        "request_id": msg.request_id,
        "sender_id": msg.sender_id,
        "sender_is_admin": msg.sender_is_admin,
        "body": msg.body,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


async def notify_ticket_created(
    db: AsyncSession,
    request: models.SupportRequest,
    user: models.User,
) -> None:
    inputs = {
        "id": request.id,
        "summary": request.summary,
        "hub_id": request.hub_id,
        "badge_id": request.badge_id,
        "description": request.description,
    }

    user_identifier = str(user.telegram_id or user.id)
    await _run_dify_workflow(inputs=inputs, user_identifier=user_identifier)


async def notify_new_message(
    db: AsyncSession,
    request: models.SupportRequest,
    message: models.SupportMessage,
    user: models.User,
) -> None:
    inputs = {
        "id": request.id,
        "summary": request.summary,
        "hub_id": request.hub_id,
        "badge_id": request.badge_id,
        "description": request.description,
    }

    user_identifier = str(user.telegram_id or user.id)
    await _run_dify_workflow(inputs=inputs, user_identifier=user_identifier)

