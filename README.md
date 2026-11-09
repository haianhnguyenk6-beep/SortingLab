# SortingLab

Ứng dụng so sánh 6 thuật toán sắp xếp, chạy thí nghiệm, đọc CSV và xuất kết quả cho Power BI.

## Khởi động

Dùng Python 3.12 để khớp môi trường kiểm thử. Trong thư mục dự án:

- Windows: mở `START.bat`, hoặc chạy `python start.py`.
- Linux/macOS: chạy `sh START.sh`.

Launcher cài NumPy và Matplotlib nếu thiếu, rồi mở dashboard cục bộ. Giữ cửa sổ launcher mở trong khi sử dụng.

## Lấy đủ dữ liệu Kaggle

Ba CSV trong `data/kaggle/` được quản lý bằng **Git LFS**. Tệp chỉ khoảng 130 byte là con trỏ LFS, chưa chứa dữ liệu gốc. Sau khi cài Git LFS, chạy trong repository:

```bash
git lfs install
git lfs pull
```

| Dataset | Đường dẫn | Cột mặc định |
| --- | --- | --- |
| Superstore | `data/kaggle/superstore/SampleSuperstore.csv` | `Sales` |
| Olist | `data/kaggle/olist/olist_order_items_dataset.csv` | `price` |
| Credit Card | `data/kaggle/creditcard/creditcard.csv` | `Amount` |

Nếu không lấy được dữ liệu LFS, tải CSV gốc từ trang Kaggle được liên kết trong **Real-life Data**, đặt vào đường dẫn tương ứng, hoặc tải CSV riêng lên giao diện.

## Chạy và xuất kết quả

1. **Experiment Data**: xem số liệu/biểu đồ đã lưu hoặc chạy thử dữ liệu mới.
2. **Real-life Data**: chọn CSV, cột số và kích thước mẫu, rồi chạy benchmark.
3. **Benchmark All**: chạy các dataset hợp lệ; báo rõ và bỏ qua dataset thiếu hoặc lỗi.
4. **Kết quả benchmark**: xem kết quả, tải Excel/CSV. **Công cụ nâng cao** có báo cáo chất lượng dữ liệu.

CSV cần tiêu đề, phân cách bằng dấu phẩy và mã hóa UTF-8. Giá trị trống/không hữu hạn bị bỏ qua. Cột số vẫn được nhận diện sau các dòng trống đầu tiên.

Ở mẫu trên 4.000 phần tử, các trường hợp có nguy cơ chi phí bậc hai được ghi `skipped`. Mỗi thuật toán CSV được chạy trong tiến trình riêng, giới hạn 15 giây cho kiểm tra đầu ra, đo thời gian và bộ nhớ. Quá hạn được ghi `timeout`, sau đó tiếp tục thuật toán khác. Lý do được giữ trong CSV xuất ra.

## Power BI

Xem [hướng dẫn Power BI](powerbi/PowerBI_Dashboard_Instructions.md). Luồng web ghi:

- Lần chạy riêng mới nhất: `results/powerbi/final_benchmark.csv`.
- Benchmark All: `results/powerbi/all_datasets_benchmark.csv`.
- Lịch sử: `results/powerbi/history.csv`.

Tệp `.pbix` cần được tạo và lưu trong Power BI Desktop.

## Kiểm tra mã nguồn

```bash
python -m pip install -r requirements.txt
python -m flake8 sortinglab tests
python -m pytest --cov --cov-report=term-missing
```

GitHub Actions chạy bộ kiểm thử trên Linux và kiểm tra riêng launcher trên Windows. Thời gian đo phụ thuộc máy và điều kiện chạy.
