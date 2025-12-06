from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from batch_runner import run_batch_once_noarg
from app.api import prices

app = FastAPI()

origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(prices.router, prefix="/api")


@app.post("/api/prices/run")
def run_prices_job():
    """
    Keepa → Amazon → 楽天 → Excel出力までを1回実行し、
    件数とExcelパスを返す。

    ※ Pricing で QuotaExceeded 疑いがある場合のみ 503 を返す。
       「候補0件」は正常完了として 200 を返す。
    """
    try:
        summary = run_batch_once_noarg()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"batch execution failed: {type(e).__name__}",
        )

    if not summary:
        raise HTTPException(
            status_code=500,
            detail="batch returned empty summary",
        )

    # Pricing側で実質全滅しているパターンだけ 503 にする
    if summary.get("pricing_quota_suspected"):
        raise HTTPException(
            status_code=503,
            detail="Amazon Pricing API quota exceeded (no or very few pricing results).",
        )

    asin_count = int(summary.get("asin_count") or 0)
    excel_path = summary.get("excel_path")

    return {
        "status": "completed",
        "asin_count": asin_count,
        "excel_path": excel_path,
        # 追加で詳細を見たいとき用
        "summary": summary,
    }


@app.get("/")
def root():
    return {"status": "ok"}
