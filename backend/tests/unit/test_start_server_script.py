import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"


def _run_import_check(*, cwd: Path, script: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CREATIVE_AGENT_STARTUP_IMPORT_CHECK"] = "1"
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, script],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )


def test_start_server_imports_app_from_repo_root():
    result = _run_import_check(
        cwd=REPO_ROOT,
        script="backend/scripts/start_server.py",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Application imported successfully" in result.stdout


def test_start_server_imports_app_from_backend_cwd():
    result = _run_import_check(
        cwd=BACKEND_DIR,
        script="scripts/start_server.py",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Application imported successfully" in result.stdout
