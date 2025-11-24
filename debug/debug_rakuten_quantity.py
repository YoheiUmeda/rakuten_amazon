import tkinter as tk
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tkinter import scrolledtext, messagebox
from utils.utils import extract_quantity_from_rakuten_title

def run_extraction():
    input_text = text_area.get("1.0", tk.END).strip()
    if not input_text:
        messagebox.showerror("エラー", "入力を空にはできません")
        return

    lines = input_text.split("\n")
    result_lines = []

    for i, title in enumerate(lines, 1):
        title = title.strip()
        if not title:
            continue
        quantity = extract_quantity_from_rakuten_title(title)
        result_lines.append(f"{i:02d}. 数量: {quantity:<2} ｜「{title}」")

    result_text = "\n".join(result_lines)
    result_area.delete("1.0", tk.END)
    result_area.insert(tk.END, result_text)

root = tk.Tk()
root.title("楽天タイトル数量抽出 デバッグ")

tk.Label(root, text="🔸楽天商品タイトル（改行区切りで複数入力可）").pack()

text_area = scrolledtext.ScrolledText(root, width=90, height=15)
text_area.pack(padx=10, pady=5)

tk.Button(root, text="✅ 数量を抽出", command=run_extraction).pack(pady=10)

tk.Label(root, text="🔽 抽出結果").pack()
result_area = scrolledtext.ScrolledText(root, width=90, height=15)
result_area.pack(padx=10, pady=5)

root.mainloop()