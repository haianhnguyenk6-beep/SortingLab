# SortingLab — nhập kết quả vào Power BI Desktop

## Chuẩn bị dữ liệu

Chạy `START.bat` hoặc `python start.py`, thực hiện benchmark rồi tải Excel/CSV từ trang kết quả.

| Luồng | CSV kết quả |
| --- | --- |
| Một CSV, lần chạy mới nhất | `results/powerbi/final_benchmark.csv` |
| Benchmark All | `results/powerbi/all_datasets_benchmark.csv` |
| Lịch sử | `results/powerbi/history.csv` |
| CLI `scripts.kaggle_pipeline --dataset superstore` | `results/powerbi/superstore_benchmark.csv` |

Nếu được báo con trỏ Git LFS, chạy `git lfs install` và `git lfs pull`, hoặc cung cấp CSV gốc. Dataset thiếu/lỗi không được thay bằng dữ liệu mô phỏng.

## Tạo dashboard

1. **Get Data > Excel workbook**: chọn Excel đã tải, chọn sheet **Benchmark**. Với CSV, chọn **Get Data > Text/CSV** và tệp tương ứng ở bảng trên.
2. Trong Power Query, đổi tên bảng thành **SortingBenchmark** để khớp DAX.
3. Đặt `n`, `repeats` thành số nguyên; `median_ms`, `min_ms`, `max_ms`, `peak_kb` thành số thập phân; `run_utc` thành Date/Time/Timezone. Các cột nhận dạng/trạng thái là Text. Giữ giá trị trống ở phép đo bị bỏ qua hoặc quá hạn.
4. Thêm từng measure trong `DAX_Measures.txt` qua **Modeling > New measure**.
5. Biểu đồ thanh: Y `algorithm`, X `median_ms`; lọc `status = ok`, sắp xếp tăng dần.
6. Biểu đồ bộ nhớ: `algorithm` và `peak_kb`; lọc `status = ok` và bỏ giá trị bộ nhớ trống.
7. KPI: Successful Runs, Median Runtime (ms), Average Peak Memory (KB), Success Rate.
8. Thêm slicer `dataset`, `column`, `n`, `run_id`; so sánh trong cùng lần chạy và cùng kích thước mẫu.
9. Bảng chi tiết cần cả `status`, `reason` để nhìn thấy phép đo bị bỏ qua/quá hạn.
10. Lưu `SortingLab_Dashboard.pbix` trong Power BI Desktop. Refresh sau khi CSV nguồn được tạo lại.

`PowerQuery_SortingBenchmark.m` là lựa chọn thay cho nhập CSV thủ công. Sửa đường dẫn theo máy của bạn; mặc định là CSV Benchmark All. Nếu kết hợp nhiều tệp, dùng Append thay vì nối chỉ theo tên thuật toán.

## Demo tùy chọn

```bash
python -m scripts.prepare_powerbi_demo
```

Lệnh tạo dữ liệu **mô phỏng** và `results/powerbi/sorting_benchmark.csv`, không phải Kaggle gốc. Tệp demo có schema cũ, ít cột hơn: nhập trực tiếp qua Text/CSV, không dùng Power Query mẫu dành cho schema đầy đủ.

Thời gian phụ thuộc máy và điều kiện đo. `peak_kb` là đỉnh cấp phát Python được theo dõi, không phải tổng RAM. Repository không có sẵn `.pbix`; cần kiểm tra báo cáo trực tiếp trong Power BI Desktop.
