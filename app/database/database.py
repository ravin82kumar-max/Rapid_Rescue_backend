from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "rapidrescue_super_secret_jwt_key_2026_safe"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    class Config:
        env_file = ".env"
        extra = "allow"


import urllib.parse


def clean_asyncpg_url(url: str) -> str:
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    parsed = urllib.parse.urlparse(url)
    if parsed.query:
        query_params = urllib.parse.parse_qs(parsed.query)
        query_params.pop("sslmode", None)
        query_params.pop("channel_binding", None)
        if "ssl" not in query_params:
            query_params["ssl"] = ["require"]
        new_query = urllib.parse.urlencode(query_params, doseq=True)
        parsed = parsed._replace(query=new_query)
        url = urllib.parse.urlunparse(parsed)
    return url


settings = Settings()
db_url = clean_asyncpg_url(settings.DATABASE_URL)

engine = create_async_engine(
    db_url,
    echo=True
)




AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session