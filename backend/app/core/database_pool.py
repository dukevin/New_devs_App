from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings


class DatabasePool:
    def __init__(self):
        self.engine = None
        self.session_factory = None

    async def initialize(self):
        database_url = make_url(settings.database_url).set(drivername="postgresql+asyncpg")
        self.engine = create_async_engine(database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def close(self):
        if self.engine:
            await self.engine.dispose()
        self.engine = None
        self.session_factory = None

    def get_session(self) -> AsyncSession:
        if self.session_factory is None:
            raise RuntimeError("Database pool not initialized")
        return self.session_factory()


db_pool = DatabasePool()


async def get_db_session():
    async with db_pool.get_session() as session:
        yield session
