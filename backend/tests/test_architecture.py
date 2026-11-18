import subprocess
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_dashboard_modules_do_not_import_each_other():
    result = subprocess.run(
        ["uv", "run", "lint-imports"], cwd=BACKEND_DIR, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stdout + result.stderr
