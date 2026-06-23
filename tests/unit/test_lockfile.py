"""
Unit tests for dependency lock file presence and sync validation.
"""

import os
import subprocess

import pytest


class TestLockFile:
    """Verify requirements.lock exists and is in sync with requirements.in."""

    def test_lock_file_exists(self):
        """GIVEN the repository root
        WHEN os.path.exists checks requirements.lock
        THEN it returns True."""
        assert os.path.exists("requirements.lock"), (
            "requirements.lock not found — run pip-compile requirements.in -o requirements.lock"
        )

    def test_lock_in_sync_with_in(self):
        """GIVEN requirements.in and requirements.lock
        WHEN pip-compile --check runs
        THEN it exits 0 (in sync).

        Skipped if pip-compile is not installed or doesn't support --check.
        """
        import shutil

        if not shutil.which("pip-compile"):
            pytest.skip("pip-compile not installed in this environment")

        # Probe whether --check is supported
        probe = subprocess.run(
            ["pip-compile", "--check", "--help"],
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            pytest.skip("pip-compile --check not available in this pip-tools version")

        result = subprocess.run(
            ["pip-compile", "--check"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"requirements.lock is out of sync with requirements.in:\n{result.stderr}"
        )
