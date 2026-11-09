"""Recognize Git LFS placeholders before treating local files as CSV data."""
from pathlib import Path


def is_lfs_pointer(path):
    with Path(path).open('rb') as stream:
        return stream.read(128).startswith(
            b'version https://git-lfs.github.com/spec/v1'
        )


def ensure_csv_data(path):
    if is_lfs_pointer(path):
        raise ValueError(
            'Tệp này chỉ là con trỏ Git LFS, chưa có dữ liệu CSV. '
            'Chạy git lfs install rồi git lfs pull trong thư mục dự án, '
            'hoặc thay bằng CSV gốc đã tải từ Kaggle.'
        )
