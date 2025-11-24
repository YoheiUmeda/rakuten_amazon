# app/init_db.py
from app.db import engine        # ★ db.py のパスに合わせる
from app.models import Base      # ★ PriceSnapshot を定義してる Base

def reset_db() -> None:
    # 既存のテーブルを全部削除（Baseにぶら下がってるもの）
    print("⚠️ 全テーブル削除中...")
    Base.metadata.drop_all(bind=engine)

    # モデル定義どおりにテーブルを再作成
    print("🛠 テーブル再作成中...")
    Base.metadata.create_all(bind=engine)

    print("✅ DB リセット完了")

if __name__ == "__main__":
    reset_db()