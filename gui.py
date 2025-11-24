import tkinter as tk

def run_analysis():
    asins = asin_text.get("1.0", tk.END).strip().splitlines()
    # ここでAPI取得・計算・Excel出力処理を呼び出す

root = tk.Tk()
root.title("ASIN価格差分析")
root.geometry("400x300")

tk.Label(root, text="ASIN（1行1つ）:").pack()
asin_text = tk.Text(root, height=10, width=40)
asin_text.pack()

tk.Button(root, text="実行", command=run_analysis).pack()
root.mainloop()