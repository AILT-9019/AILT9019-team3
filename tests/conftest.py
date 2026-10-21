import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EXTRACTOR_MODE", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
