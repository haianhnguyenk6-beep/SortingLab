"""Run the real Windows launcher with Python available but no py launcher."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Requires Windows cmd.exe')


@pytest.mark.parametrize('exit_code', [0, 7])
def test_python_fallback_and_exit_status(tmp_path, exit_code):
    system32 = Path(os.environ['SystemRoot']) / 'System32'
    env = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + str(system32))
    where = system32 / 'where.exe'
    assert subprocess.run([str(where), 'py'], env=env, capture_output=True).returncode != 0
    assert subprocess.run([str(where), 'python'], env=env, capture_output=True).returncode == 0
    launcher = tmp_path / 'START.bat'
    shutil.copyfile(Path(__file__).resolve().parents[1] / 'START.bat', launcher)
    (tmp_path / 'start.py').write_text(
        "from pathlib import Path\n"
        "Path('started.txt').write_text('started')\n"
        f"raise SystemExit({exit_code})\n", encoding='utf-8'
    )
    result = subprocess.run(
        [str(system32 / 'cmd.exe'), '/d', '/c', str(launcher)],
        cwd=tmp_path, env=env, input='\n', capture_output=True, text=True, timeout=20,
    )
    assert (tmp_path / 'started.txt').is_file(), result.stdout + result.stderr
    assert result.returncode == exit_code
