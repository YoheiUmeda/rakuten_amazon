# tests/test_design_doc_mapper.py
"""
design_doc_mapper.map_changed_files の最小テスト。
"""
import pytest

from tools.ai_orchestrator.design_doc_mapper import map_changed_files


class TestMapChangedFiles:

    def test_api_file_maps_to_api_design(self):
        result = map_changed_files(["app/api/prices.py"])
        assert "api_design" in result
        assert "app/api/prices.py" in result["api_design"]

    def test_batch_runner_maps_to_process_flow_and_system_overview(self):
        result = map_changed_files(["batch_runner.py"])
        assert "process_flow" in result
        assert "system_overview" in result

    def test_schemas_maps_to_api_design_and_data_model(self):
        result = map_changed_files(["app/schemas.py"])
        assert "api_design" in result
        assert "data_model" in result

    def test_unrelated_file_returns_empty(self):
        result = map_changed_files(["some_random_file.txt"])
        assert result == {}

    def test_empty_list_returns_empty(self):
        result = map_changed_files([])
        assert result == {}

    def test_no_duplicate_files_in_same_doc(self):
        # 同じファイルを2回渡しても重複しない
        result = map_changed_files(["app/api/prices.py", "app/api/prices.py"])
        for doc_id, files in result.items():
            assert len(files) == len(set(files)), f"{doc_id}: duplicates found"

    def test_multiple_files_accumulate_correctly(self):
        result = map_changed_files(["app/api/prices.py", "batch_runner.py"])
        assert "api_design" in result
        assert "process_flow" in result
        assert "system_overview" in result

    def test_rakuten_client_maps_to_process_flow(self):
        result = map_changed_files(["rakuten_client.py"])
        assert "process_flow" in result
        assert "rakuten_client.py" in result["process_flow"]
