import tkinter as tk
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tkinter import scrolledtext, messagebox
from utils.utils import extract_quantity_combined  # あなたの実装済み関数

def run_debug_extraction():
    input_text = title_input.get("1.0", tk.END).strip()
    if not input_text:
        messagebox.showwarning("入力エラー", "タイトルを入力してください。")
        return

    titles = input_text.splitlines()
    output_lines = []

    for idx, title in enumerate(titles, 1):
        if not title.strip():
            continue
        quantity = extract_quantity_combined(title)
        output_lines.append(f"{idx:02}. 数量: {quantity} ｜ {title.strip()}")

    result_output.delete("1.0", tk.END)
    result_output.insert(tk.END, "\n".join(output_lines))

# === GUI Setup ===
root = tk.Tk()
root.title("📦 Amazon タイトル数量抽出（debug: extract_quantity_combined）")

# 入力欄
tk.Label(root, text="🔹 Amazon 商品タイトルを複数行で入力してください").pack()
title_input = scrolledtext.ScrolledText(root, width=90, height=12)
title_input.pack(padx=10, pady=5)

# 抽出ボタン
tk.Button(root, text="✅ 数量を抽出", command=run_debug_extraction, height=2).pack(pady=10)

# 出力欄
tk.Label(root, text="🔽 抽出結果").pack()
result_output = scrolledtext.ScrolledText(root, width=90, height=12)
result_output.pack(padx=10, pady=5)

# 実行
root.mainloop()