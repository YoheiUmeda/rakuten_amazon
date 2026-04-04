# app/db.py
from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator, Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# .env 読み込み（OS環境変数を優先するため override=False）
load_dotenv(override=False)


@lru_cache(maxsize=1)
def _get_session_local():
    """
    SessionLocal を遅延生成して返す（初回呼び出し時のみ engine / sessionmaker を作成）。
    DATABASE_URL が未設定の場合はここで初めて RuntimeError を送出する。
    import 時点ではエラーにならない。
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL が設定されていません。"
            "DB保存・FastAPI を使う場合は .env に DATABASE_URL を設定してください。"
        )
    engine = create_engine(url, echo=False, future=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def get_session() -> Iterator[Session]:
    """スクリプト等で使う用（with パターン）"""
    session: Session = _get_session_local()()
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
    db: Session = _get_session_local()()
    try:
        yield db
    finally:
        db.close()
