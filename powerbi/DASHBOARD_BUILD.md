# Tạo dashboard Power BI từ SortingLab

Hướng dẫn đầy đủ: [PowerBI_Dashboard_Instructions.md](PowerBI_Dashboard_Instructions.md).

## Luồng giao diện web

1. Lấy đủ CSV gốc bằng `git lfs install` và `git lfs pull`, hoặc cung cấp CSV từ Kaggle theo README.
2. Chạy `START.bat` hoặc `python start.py`.
3. Chạy **Benchmark All**, tải Excel/CSV tổng hợp.
4. Nhập tệp trong Power BI Desktop. Đặt tên bảng **SortingBenchmark** trước khi thêm DAX.

CSV tổng hợp là `results/powerbi/all_datasets_benchmark.csv`. CSV riêng mới nhất là `results/powerbi/final_benchmark.csv`.

## Luồng dòng lệnh

Trong thư mục gốc dự án:

```bash
python -m scripts.kaggle_pipeline --dataset superstore --limit 1000 --repeats 3
```

Lệnh đọc `data/kaggle/superstore/SampleSuperstore.csv`, cột `Sales`, và ghi **`results/powerbi/superstore_benchmark.csv`**. Với `--dataset olist` hoặc `--dataset creditcard`, tên tệp xuất là `olist_benchmark.csv` hoặc `creditcard_benchmark.csv`.

Để tải qua Kaggle CLI, cài `kaggle`, cấu hình thông tin xác thực của chính bạn và thêm `--download`. Dataset mặc định là Superstore, không phải Store Item Demand Forecasting.

Khi dùng `PowerQuery_SortingBenchmark.m`, sửa đường dẫn tuyệt đối và tên CSV theo luồng đã chạy. Mẫu mặc định trỏ đến CSV **Benchmark All**. Lưu `.pbix` trực tiếp trong Power BI Desktop.
