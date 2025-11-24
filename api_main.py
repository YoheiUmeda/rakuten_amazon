# api_main.py
from fastapi import FastAPI
from app.api import prices

app = FastAPI()

# ルーター登録
app.include_router(prices.router)

# 動作確認用
@app.get("/")
def root():
    return {"status": "ok"}