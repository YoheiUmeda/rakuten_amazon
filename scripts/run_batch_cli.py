# scripts/run_batch_cli.py
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ==============================
#  プロジェクトルートを sys.path に追加
# ==============================
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ここで batch_runner を import できるようになる
from batch_runner import run_batch_once


def resolve_base_dir() -> Path:
    """プロジェクトのルートディレクトリを返す。"""
    return BASE_DIR


def load_query_files(base_dir: Path) -> List[Tuple[Path, str]]:
    """
    クエリファイル群を読み込む。

    優先順位:
      1. .env の KEEPA_QUERY_DIR で指定されたフォルダ
      2. デフォルト: base_dir/data/queries

    戻り値:
      [(ファイルパス, クエリ文字列), ...]
    """
    dir_from_env = os.getenv("KEEPA_QUERY_DIR", "").strip()

    if dir_from_env:
        qdir = Path(dir_from_env)
        if not qdir.is_absolute():
            qdir = base_dir / qdir
    else:
        qdir = base_dir / "data" / "queries"

    if not qdir.exists() or not qdir.is_dir():
        raise RuntimeError(
            f"クエリフォルダが見つかりません: {qdir}\n"
            "・.env の KEEPA_QUERY_DIR を確認するか\n"
            "・フォルダを作成してクエリファイルを置いてください。"
        )

    query_files: List[Tuple[Path, str]] = []

    for path in sorted(qdir.iterdir()):
        if not path.is_file():
            continue

        text = path.read_text(encoding="utf-8").strip()
        if not text:
            # 空ファイルはスキップ
            continue

        # 全行コメントだけのファイルはスキップ
        if all(line.strip().startswith("#") for line in text.splitlines()):
            continue

        query_files.append((path, text))

    if not query_files:
        raise RuntimeError(
            f"クエリファイルが 1 件も有効ではありません: {qdir}\n"
            "ファイル内に Product Finder の URL か selection JSON を記述してください。"
        )

    return query_files


def load_single_env_query() -> str | None:
    """
    フォルダ指定がない場合のフォールバック:
      - .env の KEEPA_FINDER_QUERY があればそれを使う
      - なければ None
    """
    q = os.getenv("KEEPA_FINDER_QUERY", "").strip()
    return q or None


def load_legacy_query_file(base_dir: Path) -> str | None:
    """
    最後のフォールバック:
    data/product_finder_query_url.txt を 1 件だけ読む（旧仕様互換）。
    """
    legacy = base_dir / "data" / "product_finder_query_url.txt"
    if not legacy.exists():
        return None
    text = legacy.read_text(encoding="utf-8").strip()
    return text or None


if __name__ == "__main__":
    base_dir = resolve_base_dir()

    # ログ設定
    log_dir = base_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"batch_cli_{ts}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    # OS環境変数を優先する。.env はOSに設定がない項目のみ補完する。
    load_dotenv(override=False)
    logger.info(f"[CLI] log file: {log_path}")

    # ① KEEPA_QUERY_DIR 指定があれば「フォルダモード」で複数実行
    try:
        query_files = load_query_files(base_dir)
        logger.info(
            f"[CLI] クエリフォルダモード: {len(query_files)} ファイルを処理します。"
        )

        per_query: list = []
        for path, query in query_files:
            logger.info(f"[CLI] === 実行開始: {path.name} ===")
            logger.info(f"[CLI] query preview: {query[:150]}...")
            s = run_batch_once(query, logger=logger, query_name=path.name)
            per_query.append((path.name, s or {}))
            logger.info(f"[CLI] === 実行終了: {path.name} ===")

        logger.info("[CLI] ===== クエリ比較サマリ =====")
        logger.info("%-52s %6s %6s %12s  %s", "query", "ASIN", "pass", "pass利益合計", "Excel")
        for name, s in per_query:
            excel = Path(s.get("excel_path") or "").name or "なし"
            logger.info(
                "%-52s %6d %6d %12.0f  %s",
                name,
                s.get("total_asins", 0),
                s.get("pass_filter_count", 0),
                s.get("pass_profit_total_sum", 0),
                excel,
            )

        # .ai/handoff/ にサマリ JSON を保存
        handoff_dir = base_dir / ".ai" / "handoff"
        handoff_dir.mkdir(parents=True, exist_ok=True)

        def _rel(p: str) -> str:
            try:
                return str(Path(p).relative_to(base_dir))
            except ValueError:
                return str(p)

        summary_data = {
            "schema_version": 1,
            "timestamp": ts,
            "queries": [
                {
                    "query_name": name,
                    "total_asins": s.get("total_asins", 0),
                    "pass_filter_count": s.get("pass_filter_count", 0),
                    "pass_profit_total_sum": s.get("pass_profit_total_sum", 0),
                    "reject_reason_counts": s.get("reject_reason_counts", {}),
                    "deal_status_counts": s.get("deal_status_counts", {}),
                    "excel_path": _rel(s["excel_path"]) if s.get("excel_path") else None,
                }
                for name, s in per_query
            ],
        }
        payload = json.dumps(summary_data, ensure_ascii=False, indent=2)
        ts_path = handoff_dir / f"batch_summary_{ts}.json"
        latest_path = handoff_dir / "batch_summary_latest.json"
        try:
            ts_path.write_text(payload, encoding="utf-8")
            latest_path.write_text(payload, encoding="utf-8")
            logger.info("[CLI] サマリJSON保存: %s", ts_path)
        except OSError as e:
            logger.warning("[CLI] サマリJSON保存失敗（主処理は継続）: %s", e)

    except RuntimeError as e:
        # フォルダが見つからない / ファイルなし の場合だけフォールバックに進む
        logger.warning(
            "[CLI] KEEPA_QUERY_DIR モードが使えないためフォールバック: %s",
            e,
        )

        # ② KEEPA_FINDER_QUERY 環境変数（単発モード）
        env_query = load_single_env_query()
        if env_query:
            logger.info("[CLI] 単一クエリモード(.env KEEPA_FINDER_QUERY)")
            logger.info(f"[CLI] query preview: {env_query[:150]}...")
            run_batch_once(env_query, logger=logger)
        else:
            # ③ 旧仕様: data/product_finder_query_url.txt 1 件だけ
            legacy_query = load_legacy_query_file(base_dir)
            if legacy_query:
                logger.info("[CLI] legacy クエリファイルモード")
                logger.info(f"[CLI] query preview: {legacy_query[:150]}...")
                run_batch_once(legacy_query, logger=logger)
            else:
                logger.error(
                    "[CLI] 実行可能なクエリが見つかりません。\n"
                    "・.env の KEEPA_QUERY_DIR でフォルダを指定するか\n"
                    "・.env に KEEPA_FINDER_QUERY を直書きするか\n"
                    "・data/product_finder_query_url.txt を用意してください。"
                )
