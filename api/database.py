import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "mysql+pymysql://root:RootPass2024!@192.168.32.135/appdb")
WORKER_THREADS = int(os.environ.get("WORKER_THREADS", 4))

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=WORKER_THREADS,
    max_overflow=WORKER_THREADS,
    pool_timeout=30,
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()