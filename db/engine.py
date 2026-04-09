from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from config import settings
from db.models import Base

engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_timeout=10,
    pool_recycle=300,
    pool_pre_ping=True,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        yield session
