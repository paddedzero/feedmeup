import sys
from pathlib import Path
import importlib

# ensure repo root is on sys.path so fetch_news.py can be imported
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

def test_import_fetch_news():
    mod = importlib.import_module("fetch_news")
    assert mod is not None

def test_module_constants():
    import fetch_news
    assert hasattr(fetch_news, "CONFIG_FILE")
    assert isinstance(fetch_news.CONFIG_FILE, str)
    assert hasattr(fetch_news, "POSTS_DIR")
    from pathlib import Path as _P
    assert isinstance(fetch_news.POSTS_DIR, _P)