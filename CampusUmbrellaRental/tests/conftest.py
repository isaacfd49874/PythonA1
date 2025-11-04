
import os
import sys
import pathlib
import pytest

# Ensure the project root (parent of tests/) is on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

@pytest.fixture
def app(tmp_path, monkeypatch):
    """
    Fresh app module instance and empty DATA_DIR for each test.
    Ensures UMBRELLA_DATA_DIR is set before import, so the module picks it up.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UMBRELLA_DATA_DIR", str(data_dir))

    # Force a clean import so DATA_DIR is read from env var on import
    if "main" in sys.modules:
        del sys.modules["main"]
    import main as app

    # Seed CSVs and reset time offset
    app.ensure_data_dir_and_seed()
    app.set_time_offset_seconds(0)

    yield app

    app.set_time_offset_seconds(0)
