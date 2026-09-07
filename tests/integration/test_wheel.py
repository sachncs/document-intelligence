"""Wheel install + CLI smoke test in a clean venv.

Skipped unless ``RUN_WHEEL_INSTALL_TEST=1`` is set in the env, since it
spins up a fresh venv and installs the built wheel.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_RUN = os.environ.get("RUN_WHEEL_INSTALL_TEST") == "1"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_wheel() -> Path:
    """Run `python -m build --wheel` and return the path to the .whl file."""
    out = _project_root() / "dist"
    if (out / "docendo-0.3.0a1-py3-none-any.whl").exists():
        return out / "docendo-0.3.0a1-py3-none-any.whl"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel"],
        cwd=_project_root(),
        check=True,
    )
    wheels = sorted(out.glob("docendo-*.whl"))
    assert wheels, "no wheel built"
    return wheels[-1]


@pytest.mark.skipif(not _RUN, reason="Set RUN_WHEEL_INSTALL_TEST=1 to run")
class TestWheelInstall:
    def test_install_and_help(self) -> None:
        wheel = _build_wheel()
        with tempfile.TemporaryDirectory() as tmp:
            venv = Path(tmp) / "venv"
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv)], check=True
            )
            py = venv / "bin" / "python"
            subprocess.run(
                [str(py), "-m", "pip", "install", "--quiet", str(wheel), "beautifulsoup4", "gigatoken"],
                check=True,
            )
            result = subprocess.run(
                [str(venv / "bin" / "docendo"), "--help"],
                capture_output=True,
                text=True,
                check=True,
            )
            assert "fetch" in result.stdout
            assert "ingest" in result.stdout
            assert "eval" in result.stdout
            assert "report" in result.stdout
            assert "demo" in result.stdout
            assert "cases" in result.stdout
            assert "checkup" in result.stdout
        # shutil.rmtree isn't needed; tempfile cleans itself up
        assert True
