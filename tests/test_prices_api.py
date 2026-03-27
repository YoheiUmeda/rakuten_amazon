# tests/test_prices_api.py
"""
app/api/prices.search_prices の ASIN ごと最新1件フィルタのテスト。

- FastAPI TestClient を使わず、SQLite in-memory セッションを直接渡す。
- Base.metadata.create_all でテーブルを都度作成し、テスト間の独立性を保つ。
"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, PriceSnapshot
from app.schemas import PriceSearchCondition
from app.api.prices import search_prices


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _snap(asin: str, title: str, profit: float, checked_at: datetime) -> PriceSnapshot:
    return PriceSnapshot(
        asin=asin,
        title=title,
        profit_per_item=profit,
        roi_percent=10.0,
        pass_filter=True,
        checked_at=checked_at,
    )


T_OLD = datetime(2024, 1, 1, 10, 0, 0)
T_NEW = datetime(2024, 1, 1, 12, 0, 0)


class TestLatestSnapshotPerAsin:

    def test_returns_only_latest_row_per_asin(self, db):
        """同一 ASIN が複数あっても最新1件（id 最大行）だけ返る"""
        db.add_all([
            _snap("B001", "old_title", profit=1000.0, checked_at=T_OLD),
            _snap("B001", "new_title", profit=1200.0, checked_at=T_NEW),
        ])
        db.commit()

        result = search_prices(PriceSearchCondition(), db=db)

        assert result.total == 1
        assert result.items[0].title == "new_title"

    def test_old_row_passes_min_profit_but_latest_does_not(self, db):
        """古い行は min_profit を満たすが最新行は満たさない → そのASINは返らない"""
        db.add_all([
            _snap("B002", "old_rich", profit=2000.0, checked_at=T_OLD),
            _snap("B002", "new_poor", profit=50.0,   checked_at=T_NEW),
        ])
        db.commit()

        result = search_prices(PriceSearchCondition(min_profit=500.0), db=db)

        assert result.total == 0


class TestPassFilterInResponse:

    def test_pass_filter_is_returned_in_items(self, db):
        """レスポンスの各 item に pass_filter が含まれること"""
        db.add_all([
            PriceSnapshot(asin="B003", title="candidate", profit_per_item=1000.0,
                          roi_percent=30.0, pass_filter=True,  checked_at=T_NEW),
            PriceSnapshot(asin="B004", title="rejected",  profit_per_item=100.0,
                          roi_percent=5.0,  pass_filter=False, checked_at=T_NEW),
        ])
        db.commit()

        result = search_prices(PriceSearchCondition(), db=db)

        by_asin = {item.asin: item for item in result.items}
        assert by_asin["B003"].pass_filter is True
        assert by_asin["B004"].pass_filter is False


class TestPassFilterSortPriority:

    def test_pass_filter_true_comes_before_higher_profit_false(self, db):
        """profit が低くても pass_filter=True の商品が pass_filter=False より先に返る"""
        db.add_all([
            PriceSnapshot(asin="B005", title="high_profit_rejected",
                          profit_per_item=9999.0, roi_percent=50.0,
                          pass_filter=False, checked_at=T_NEW),
            PriceSnapshot(asin="B006", title="low_profit_candidate",
                          profit_per_item=100.0, roi_percent=10.0,
                          pass_filter=True, checked_at=T_NEW),
        ])
        db.commit()

        result = search_prices(PriceSearchCondition(), db=db)

        assert result.items[0].asin == "B006"   # pass_filter=True が先頭
        assert result.items[1].asin == "B005"
