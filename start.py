"""One-command SortingLab launcher; standard library only until app starts."""
from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.venv'
MODULES = ('numpy', 'matplotlib')

def python_in_venv():
    return VENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')

def main():
    print('=== SortingLab FINAL ===', flush=True)
    if sys.version_info < (3, 10):
        print('Yêu cầu Python 3.10 trở lên. Cài Python từ python.org và chạy lại.')
        return 1
    if os.environ.get('SORTINGLAB_BOOTSTRAPPED') != '1' and any(importlib.util.find_spec(m) is None for m in MODULES):
        try:
            print('Đang tạo môi trường và cài thư viện cần thiết (chỉ lần đầu)...', flush=True)
            if not python_in_venv().exists():
                venv.EnvBuilder(with_pip=True).create(VENV)
            subprocess.check_call([str(python_in_venv()), '-m', 'pip', 'install', 'numpy>=1.24', 'matplotlib>=3.7'], cwd=ROOT)
            env = os.environ.copy()
            env['SORTINGLAB_BOOTSTRAPPED'] = '1'
            return subprocess.call([str(python_in_venv()), str(ROOT / 'start.py')], cwd=ROOT, env=env)
        except (OSError, subprocess.CalledProcessError) as exc:
            print('Không thể cài thư viện:', exc)
            print('Kiểm tra kết nối Internet, sau đó chạy lại START.bat.')
            return 1
    try:
        from dashboard.server import main as run_server
        run_server()
        return 0
    except ImportError as exc:
        print('Thiếu thư viện:', exc)
        print('Hãy chạy: python -m pip install -r requirements.txt')
        return 1

if __name__ == '__main__':
    sys.exit(main())
