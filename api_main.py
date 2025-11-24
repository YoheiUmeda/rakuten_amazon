# api_main.py
from fastapi import FastAPI
from app.api import prices

app = FastAPI()

# ルーター登録
app.include_router(prices.router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}
