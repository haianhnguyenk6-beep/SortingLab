"""Offline Windows GUI for CSV-based sorting benchmarks."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from sortinglab.real_data_plus import run_csv, numeric_columns


class App:
    def __init__(self, root):
        self.root = root
        root.title("Sorting Lab | Kaggle CSV & Power BI")
        root.geometry("950x610")
        self.path = tk.StringVar()
        self.column = tk.StringVar()
        self.limit = tk.StringVar(value="1000")
        self.repeats = tk.StringVar(value="3")
        frame = ttk.Frame(root, padding=15)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="Sorting Lab — Real-world CSV Benchmark",
            font=(
                "Segoe UI",
                16,
                "bold")).pack(
            anchor="w",
            pady=8)
        line = ttk.Frame(frame)
        line.pack(fill="x", pady=5)
        ttk.Entry(line, textvariable=self.path).pack(side="left", fill="x", expand=True)
        ttk.Button(line, text="Chọn CSV", command=self.choose).pack(side="left", padx=6)
        line2 = ttk.Frame(frame)
        line2.pack(fill="x", pady=8)
        ttk.Label(line2, text="Cột số:").pack(side="left")
        self.combo = ttk.Combobox(line2, textvariable=self.column, state="readonly", width=24)
        self.combo.pack(side="left", padx=6)
        ttk.Label(line2, text="Giới hạn dòng:").pack(side="left")
        ttk.Entry(line2, textvariable=self.limit, width=9).pack(side="left", padx=6)
        ttk.Label(line2, text="Số lần chạy:").pack(side="left")
        ttk.Entry(line2, textvariable=self.repeats, width=6).pack(side="left", padx=6)
        ttk.Button(
            frame,
            text="Chạy benchmark và xuất CSV Power BI",
            command=self.run).pack(
            anchor="w",
            pady=12)
        self.table = ttk.Treeview(
            frame,
            columns=(
                "algorithm",
                "n",
                "median_ms",
                "peak_kb",
                "status"),
            show="headings")
        for col in self.table['columns']:
            self.table.heading(col, text=col)
            self.table.column(col, width=160)
        self.table.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="Chọn file CSV Kaggle tải về máy hoặc dữ liệu demo.")
        ttk.Label(frame, textvariable=self.status, wraplength=900).pack(anchor="w", pady=8)

    def choose(self):
        p = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not p:
            return
        self.path.set(p)
        try:
            candidates = numeric_columns(p)
            self.combo['values'] = list(dict.fromkeys(candidates))
            self.column.set(candidates[0] if candidates else '')
            if not candidates:
                messagebox.showwarning('CSV', 'Không tìm thấy cột số trong mẫu dữ liệu.')
        except Exception as exc:
            messagebox.showerror('Lỗi CSV', str(exc))

    def run(self):
        try:
            if not self.path.get() or not self.column.get():
                raise ValueError('Chọn CSV và cột số trước.')
            out = Path(__file__).resolve().parents[1] / \
                'results' / 'powerbi' / 'sorting_benchmark.csv'
            rows = run_csv(
                self.path.get(), self.column.get(), out, int(
                    self.limit.get()), int(
                    self.repeats.get()))
            for item in self.table.get_children():
                self.table.delete(item)
            for r in rows:
                self.table.insert(
                    '',
                    'end',
                    values=[
                        r.get(
                            k,
                            '') for k in (
                            'algorithm',
                            'n',
                            'median_ms',
                            'peak_kb',
                            'status')])
            self.status.set('Đã xuất: ' + str(out) + ' | Power BI Desktop > Get Data > Text/CSV')
        except Exception as exc:
            messagebox.showerror('Không thể benchmark', str(exc))


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
