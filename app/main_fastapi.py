# app/main_fastapi.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from batch_runner import run_batch_once_noarg
from app.api import prices  # ← 追加

app = FastAPI()

origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 検索API (/api/prices) を有効化
app.include_router(prices.router, prefix="/api")

@app.post("/api/prices/run")
def run_prices_job():
    """
    Keepa → Amazon → 楽天 → Excel出力までを1回実行し、
    件数とExcelパスを返す。
    """
    summary = run_batch_once_noarg()

    asin_count = int(
        summary.get("asin_count")
        or summary.get("total_asins")
        or 0
    )
    excel_path = summary.get("excel_path")

    return {
        "status": "completed",
        "asin_count": asin_count,
        "excel_path": excel_path,
    }


@app.get("/")
def root():
    return {"status": "ok"}
