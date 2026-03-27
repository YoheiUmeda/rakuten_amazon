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


class TestDynamicPassFilter:

    def test_pass_min_profit_overrides_db_flag(self, db):
        """pass_min_profit 指定時は DB の pass_filter を無視して動的判定する"""
        db.add_all([
            PriceSnapshot(asin="C001", title="rich_rejected",
                          profit_per_item=1500.0, roi_percent=20.0,
                          pass_filter=False, checked_at=T_NEW),
            PriceSnapshot(asin="C002", title="poor_candidate",
                          profit_per_item=300.0, roi_percent=5.0,
                          pass_filter=True, checked_at=T_NEW),
        ])
        db.commit()

        result = search_prices(PriceSearchCondition(pass_min_profit=1000.0), db=db)

        by_asin = {item.asin: item for item in result.items}
        assert by_asin["C001"].pass_filter is True   # DB=False だが動的=True
        assert by_asin["C002"].pass_filter is False  # DB=True  だが動的=False

    def test_only_pass_filter_uses_dynamic_threshold(self, db):
        """only_pass_filter=True + pass_min_profit → 動的判定で絞り込む"""
        db.add_all([
            PriceSnapshot(asin="C003", title="rich",
                          profit_per_item=1500.0, roi_percent=20.0,
                          pass_filter=False, checked_at=T_NEW),
            PriceSnapshot(asin="C004", title="poor",
                          profit_per_item=300.0, roi_percent=5.0,
                          pass_filter=True, checked_at=T_NEW),
        ])
        db.commit()

        result = search_prices(
            PriceSearchCondition(pass_min_profit=1000.0, only_pass_filter=True), db=db
        )

        assert result.total == 1
        assert result.items[0].asin == "C003"

    def test_none_profit_fails_dynamic_pass(self, db):
        """profit_per_item が None の行は pass_min_profit 指定時に動的判定で不合格"""
        db.add_all([
            PriceSnapshot(asin="C005", title="no_profit",
                          profit_per_item=None, roi_percent=20.0,
                          pass_filter=True, checked_at=T_NEW),
        ])
        db.commit()

        result = search_prices(PriceSearchCondition(pass_min_profit=1.0), db=db)

        assert result.items[0].pass_filter is False

    def test_none_profit_excluded_by_only_pass_filter(self, db):
        """profit_per_item が None の行は only_pass_filter=True + 閾値指定時に除外される"""
        db.add_all([
            PriceSnapshot(asin="C006", title="no_profit",
                          profit_per_item=None, roi_percent=20.0,
                          pass_filter=True, checked_at=T_NEW),
        ])
        db.commit()

        result = search_prices(
            PriceSearchCondition(pass_min_profit=1.0, only_pass_filter=True), db=db
        )

        assert result.total == 0

    def test_none_roi_fails_dynamic_pass(self, db):
        """roi_percent が None の行は pass_min_roi 指定時に動的判定で不合格"""
        db.add_all([
            PriceSnapshot(asin="C007", title="no_roi",
                          profit_per_item=1500.0, roi_percent=None,
                          pass_filter=True, checked_at=T_NEW),
        ])
        db.commit()

        result = search_prices(PriceSearchCondition(pass_min_roi=10.0), db=db)

        assert result.items[0].pass_filter is False

    def test_only_pass_filter_uses_pass_min_roi(self, db):
        """only_pass_filter=True + pass_min_roi → ROI閾値で絞り込む"""
        db.add_all([
            PriceSnapshot(asin="C008", title="high_roi",
                          profit_per_item=500.0, roi_percent=20.0,
                          pass_filter=False, checked_at=T_NEW),
            PriceSnapshot(asin="C009", title="low_roi",
                          profit_per_item=2000.0, roi_percent=5.0,
                          pass_filter=True, checked_at=T_NEW),
        ])
        db.commit()

        result = search_prices(
            PriceSearchCondition(pass_min_roi=10.0, only_pass_filter=True), db=db
        )

        assert result.total == 1
        assert result.items[0].asin == "C008"

    def test_pass_min_profit_and_roi_and_condition(self, db):
        """pass_min_profit + pass_min_roi のAND条件: 両方満たさないと不合格"""
        db.add_all([
            PriceSnapshot(asin="C010", title="both_ok",
                          profit_per_item=1500.0, roi_percent=20.0,
                          pass_filter=False, checked_at=T_NEW),
            PriceSnapshot(asin="C011", title="profit_only",
                          profit_per_item=1500.0, roi_percent=5.0,
                          pass_filter=False, checked_at=T_NEW),
            PriceSnapshot(asin="C012", title="roi_only",
                          profit_per_item=300.0, roi_percent=20.0,
                          pass_filter=False, checked_at=T_NEW),
        ])
        db.commit()

        result = search_prices(
            PriceSearchCondition(pass_min_profit=1000.0, pass_min_roi=10.0), db=db
        )

        by_asin = {item.asin: item for item in result.items}
        assert by_asin["C010"].pass_filter is True   # 両方OK
        assert by_asin["C011"].pass_filter is False  # ROI不足
        assert by_asin["C012"].pass_filter is False  # 利益不足
