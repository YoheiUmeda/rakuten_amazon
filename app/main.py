# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import prices as prices_api
from batch_runner import run_batch_once_noarg

app = FastAPI()

origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 検索API
app.include_router(prices_api.router)

# バッチ実行API
@app.post("/api/prices/run")
def run_prices_job():
    summary = run_batch_once_noarg()
    return {
        "status": "completed",
        **(summary or {}),
    }

@app.get("/")
def root():
    return {"status": "ok"}
