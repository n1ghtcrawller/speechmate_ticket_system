from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TelegramLoginRequest(BaseModel):
    init_data: str
    ref_code: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str
    is_new: bool


class UserBase(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserCreate(UserBase):
    telegram_id: int


class UserOut(UserBase):
    id: int
    telegram_id: int
    is_active: Optional[bool] = None
    is_admin: bool
    verified_status: str
    created_at: datetime

    class Config:
        orm_mode = True


class ProfileUpdate(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class SupportRequestBase(BaseModel):
    summary: str
    hub_id: str
    badge_id: Optional[str] = None
    description: str


class SupportRequestCreate(SupportRequestBase):
    pass


class SupportRequestOut(SupportRequestBase):
    id: int
    user_id: int
    date: datetime
    # Для удобства фронта можно потом добавить сюда messages

    class Config:
        orm_mode = True


class SupportMessageBase(BaseModel):
    body: str


class SupportMessageCreate(SupportMessageBase):
    pass


class SupportMessageOut(SupportMessageBase):
    id: int
    request_id: int
    sender_id: Optional[int]
    sender_is_admin: bool
    created_at: datetime

    class Config:
        orm_mode = True
