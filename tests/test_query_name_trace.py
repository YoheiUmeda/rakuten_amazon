# tests/test_query_name_trace.py
"""query_name が Excel ファイル名・ログに伝播することを確認する最小テスト。"""
from __future__ import annotations

import os
import unittest.mock as mock
from pathlib import Path
from typing import Any, Dict


# ── excel_exporter ────────────────────────────────────────────────────────────

class TestExportAsinDictToExcel:

    def _minimal_data(self) -> Dict[str, Dict[str, Any]]:
        return {"B00TEST1234": {"pass_filter": True, "title": "テスト商品"}}

    def test_query_name_appears_in_filename(self, tmp_path, monkeypatch):
        """query_name を渡すと Excel ファイル名に stem が含まれる。"""
        monkeypatch.setenv("OUTPUT_DIR_PATH", str(tmp_path))
        from excel_exporter import export_asin_dict_to_excel
        path = export_asin_dict_to_excel(
            self._minimal_data(),
            query_name="pf_jp_no_amazon_rank15k_4k15k_v1.txt",
        )
        assert path is not None
        assert "pf_jp_no_amazon_rank15k_4k15k_v1" in Path(path).name
        assert path.endswith(".xlsx")

    def test_no_query_name_falls_back_to_output(self, tmp_path, monkeypatch):
        """query_name なし → ファイル名が 'output' を含む（既存挙動）。"""
        monkeypatch.setenv("OUTPUT_DIR_PATH", str(tmp_path))
        from excel_exporter import export_asin_dict_to_excel
        path = export_asin_dict_to_excel(self._minimal_data())
        assert path is not None
        assert "output" in Path(path).name

    def test_query_name_stem_only_no_extension_duplication(self, tmp_path, monkeypatch):
        """stem のみ使われ、.txt が二重にならない。"""
        monkeypatch.setenv("OUTPUT_DIR_PATH", str(tmp_path))
        from excel_exporter import export_asin_dict_to_excel
        path = export_asin_dict_to_excel(
            self._minimal_data(),
            query_name="my_query.txt",
        )
        assert path is not None
        name = Path(path).name
        assert ".txt" not in name
        assert "my_query" in name


# ── batch_runner.run_batch_once ───────────────────────────────────────────────

class TestRunBatchOnceQueryName:

    def _make_patch(self, monkeypatch, tmp_path):
        """run_batch_once の外部依存をすべてモックする。"""
        monkeypatch.setenv("OUTPUT_DIR_PATH", str(tmp_path))

        monkeypatch.setattr("batch_runner.get_asins_from_finder", lambda q: ["B00TEST1234"])
        monkeypatch.setattr("batch_runner.get_amazon_prices", lambda asins: {
            "B00TEST1234": {"price": 5000, "is_fba": True, "sales_rank_drops30": 10}
        })
        monkeypatch.setattr("batch_runner.get_amazon_fees_estimate", lambda d: d)
        monkeypatch.setattr("batch_runner.prefilter_for_rakuten", lambda d, **kw: (d, {}))
        monkeypatch.setattr("batch_runner.get_rakuten_info", lambda d: d)
        monkeypatch.setattr("batch_runner.calculate_price_difference", lambda d: {})
        monkeypatch.setattr("batch_runner.save_price_results", lambda r: None)

    def test_query_name_passed_to_excel(self, monkeypatch, tmp_path):
        """query_name が run_batch_once → export_asin_dict_to_excel へ伝播する。"""
        self._make_patch(monkeypatch, tmp_path)

        captured: dict = {}

        def fake_export(asin_data, query_name=None):
            captured["query_name"] = query_name
            return None

        monkeypatch.setattr("batch_runner.export_asin_dict_to_excel", fake_export)

        import batch_runner
        batch_runner.run_batch_once("dummy_query", query_name="my_query.txt")
        assert captured["query_name"] == "my_query.txt"

    def test_query_name_none_by_default(self, monkeypatch, tmp_path):
        """query_name 省略時は None が export に渡る（既存挙動維持）。"""
        self._make_patch(monkeypatch, tmp_path)

        captured: dict = {}

        def fake_export(asin_data, query_name=None):
            captured["query_name"] = query_name
            return None

        monkeypatch.setattr("batch_runner.export_asin_dict_to_excel", fake_export)

        import batch_runner
        batch_runner.run_batch_once("dummy_query")
        assert captured["query_name"] is None

    def test_query_name_in_log(self, monkeypatch, tmp_path, caplog):
        """query_name がログの開始メッセージに含まれる。"""
        import logging
        self._make_patch(monkeypatch, tmp_path)
        monkeypatch.setattr("batch_runner.export_asin_dict_to_excel", lambda d, **kw: None)

        import batch_runner
        with caplog.at_level(logging.INFO):
            batch_runner.run_batch_once("dummy_query", query_name="pf_jp_v1.txt")

        assert any("pf_jp_v1.txt" in r.message for r in caplog.records)
