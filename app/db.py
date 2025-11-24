# app/db.py
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# .env 読み込み
load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL が設定されていません")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


@contextmanager
def get_session() -> Iterator[Session]:
    """スクリプト等で使う用（with パターン）"""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except:  # noqa: E722
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI の Depends 用。
    例: def endpoint(db: Session = Depends(get_db)):
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
