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
    Points UMBRELLA_DATA_DIR at a temp ./Data_csv under pytest's tmp_path.
    """
    data_dir = tmp_path / "Data_csv"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UMBRELLA_DATA_DIR", str(data_dir))

    # Re-import main so it picks up the env var-set DATA_DIR
    if "main" in sys.modules:
        del sys.modules["main"]
    import main as app

    # Seed CSVs and reset time offset
    app.ensure_data_dir_and_seed()
    app.set_time_offset_seconds(0)

    yield app

    # Teardown time offset (CSV temp dir is auto-removed by pytest)
    app.set_time_offset_seconds(0)
