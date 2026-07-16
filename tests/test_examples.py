"""
Example execution tests.

Verifies all example scripts run without errors.
"""
import pytest
import subprocess
import sys
from pathlib import Path


# Get the project root
PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"


def test_example_00_high_level_api():
    """Test examples/00_high_level_api.py runs successfully."""
    example_path = EXAMPLES_DIR / "00_high_level_api.py"
    assert example_path.exists(), f"Example not found: {example_path}"

    # Run the example
    result = subprocess.run(
        [sys.executable, str(example_path)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env={
            **subprocess.os.environ,
            "PYTHONPATH": str(PROJECT_ROOT / "src")
        },
        timeout=30
    )

    # Check it ran successfully
    assert result.returncode == 0, f"Example failed:\n{result.stderr}"
    assert "✓ Example complete" in result.stdout or "✓ High-level API demonstration complete" in result.stdout


def test_example_01_basic_usage():
    """Test examples/01_basic_usage.py runs successfully."""
    example_path = EXAMPLES_DIR / "01_basic_usage.py"
    assert example_path.exists(), f"Example not found: {example_path}"

    result = subprocess.run(
        [sys.executable, str(example_path)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env={
            **subprocess.os.environ,
            "PYTHONPATH": str(PROJECT_ROOT / "src")
        },
        timeout=30
    )

    assert result.returncode == 0, f"Example failed:\n{result.stderr}"
    assert "✓ Example complete" in result.stdout


def test_all_examples_have_main_guard():
    """Test all Python files in examples/ have if __name__ == '__main__' guard."""
    example_files = list(EXAMPLES_DIR.glob("*.py"))

    # Exclude __init__.py
    example_files = [f for f in example_files if f.name != "__init__.py"]

    assert len(example_files) >= 2, "Should have at least 2 examples"

    for example_file in example_files:
        content = example_file.read_text()
        assert 'if __name__ == "__main__"' in content or 'if __name__ == \'__main__\'' in content, \
            f"{example_file.name} missing main guard"


def test_example_fixtures_importable():
    """Test that fixture modules can be imported."""
    # This tests examples/fixtures/__init__.py exists and is valid
    from examples.fixtures import healthy_session

    # Should have expected exports
    assert hasattr(healthy_session, "HEALTHY_SESSION_SPANS")
    assert hasattr(healthy_session, "SESSION_ID")
