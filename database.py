from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base


# Асинхронная строка подключения с aiosqlite
DATABASE_URL = "sqlite+aiosqlite:///./support_bot.db"

# Создаем асинхронный движок для SQLite
async_engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()



async def init_db():
    from models.models import User, SupportRequest, SupportMessage
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)