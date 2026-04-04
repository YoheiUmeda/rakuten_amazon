# tests/test_import_excel_to_db.py
"""import_excel_to_db の HEADER_MAP_JA 整合性チェックのテスト。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import import_excel_to_db as m


def test_validate_header_mapping_passes():
    """現在の _JA_TO_KEY は HEADER_MAP_JA と整合している。"""
    m._validate_header_mapping()  # raises なければ OK


def test_validate_header_mapping_detects_mismatch(monkeypatch):
    """HEADER_MAP_JA["price"] が変わると ValueError になる。"""
    monkeypatch.setitem(m._EXCEL_HEADER_MAP, "price", "別ラベル")
    with pytest.raises(ValueError, match="amazon_price"):
        m._validate_header_mapping()
