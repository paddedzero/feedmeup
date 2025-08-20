import importlib
import pathlib

def test_import_fetch_news():
    # ensure module imports without running main
    mod = importlib.import_module("fetch_news")
    assert mod is not None

def test_module_constants():
    import fetch_news
    # basic sanity checks for important constants
    assert hasattr(fetch_news, "CONFIG_FILE")
    assert isinstance(fetch_news.CONFIG_FILE, str)
    assert hasattr(fetch_news, "POSTS_DIR")
    assert isinstance(fetch_news.POSTS_DIR, pathlib.Path)