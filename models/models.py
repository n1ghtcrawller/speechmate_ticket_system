from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, BigInteger
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import uuid


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    verified_status = Column(String(50), default="pending")  # "unverified", "pending", "approved", "rejected"
    created_at = Column(DateTime, default=datetime.utcnow)

    # Новые поля для реферальной системы
    ref_code = Column(String, unique=True, index=True, default=lambda: uuid.uuid4().hex[:8])
    invited_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Связь с обращениями
    support_requests = relationship("SupportRequest", back_populates="user", cascade="all, delete-orphan")


class SupportRequest(Base):
    __tablename__ = "support_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    summary = Column(String(255), nullable=False)
    hub_id = Column(String(255), nullable=False)
    badge_id = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="support_requests")
    messages = relationship("SupportMessage", back_populates="request", cascade="all, delete-orphan")


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("support_requests.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sender_is_admin = Column(Boolean, default=False, nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    request = relationship("SupportRequest", back_populates="messages")
