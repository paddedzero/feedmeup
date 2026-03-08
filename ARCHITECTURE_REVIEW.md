# Architecture Review & Improvement Plan

**Date:** March 7, 2026  
**Scope:** Full codebase review — QA validation, security audit, and architectural improvements  
**Status:** Actionable recommendations for next iteration

---

## ✅ Issues Found & Fixed in This Review

### Security Fixes (High Priority — Applied)
| Issue | File | Fix Applied |
|-------|------|-------------|
| XSS via article titles/summaries in HTML output | `scripts/fetch_news.py` | Added `html.escape()` to all 5 HTML-generation sites |
| XSS via source names in multi-source list | `scripts/fetch_news.py` | Added `html_escape()` to `_render_source_list_html()` |
| Unescaped `feed_url`/`error_message` in error post bodies | `scripts/fetch_news.py` | Added HTML entity encoding before Markdown write |
| Mermaid `securityLevel: 'loose'` allows JS execution in diagrams | `src/components/Mermaid.svelte` | Changed to `'strict'` |

### Test Fixes (Applied)
| Issue | File | Fix Applied |
|-------|------|-------------|
| `test_tagging_dashboard.py` silently shows `✗ Contains emerging section` | `test_tagging_dashboard.py` | Added cross-source "container-security" tag to trigger EMERGING section |
| `test_regex.py` matched 0 articles (stale regex pattern) | `test_regex.py` | Updated regex to match current file format (no `<a href>` tags in bullet list) |
| CRITICAL TRENDS label said "5+ sources tracked" but included highlight-boosted items | `scripts/fetch_news.py` | Updated label to "high-frequency or widely covered" |

---

## 🏗️ Architectural Improvement Recommendations

### 1. Break Up `fetch_news.py` (3,284 lines → multiple modules)

**Problem:** `fetch_news.py` is a monolith that handles config loading, HTTP, filtering, deduplication, Gemini AI, HTML generation, and file I/O. This makes it hard to test, maintain, and reason about.

**Recommendation:** Extract into focused modules:

```
scripts/
  fetch_news.py          # Main orchestration (< 300 lines)
  lib/
    config.py            # Config loading + defaults
    feed_fetcher.py      # HTTP session, fetch_feed_entries()
    filters.py           # keyword matching, negative keywords
    deduplication.py     # fuzzy + semantic dedup
    html_generator.py    # format_entries_for_category(), highlights
    post_writer.py       # write_dual_output(), save_error_post()
    gemini_client.py     # Gemini API wrapper
    scraper_utils.py     # already separate in scraper.py ✅
```

**Benefit:** Each module can be independently unit-tested. `html_generator.py` in particular needs thorough tests for HTML escaping.

---

### 2. Convert Ad-Hoc Test Scripts to Proper pytest Tests

**Problem:** Tests are standalone scripts with `if __name__ == "__main__"` patterns. They don't fail CI (no exit code 1 on assertion failure in some tests), aren't discovered by pytest automatically, and have no test isolation.

**Recommendation:**
```
tests/
  test_filters.py        # pytest: keyword matching, negative keywords
  test_dedup.py          # pytest: fuzzy + semantic dedup ✅ (already partly done)
  test_html_gen.py       # pytest: XSS escaping, format_entries_for_category
  test_sanitize_url.py   # pytest: URL sanitization edge cases
  test_config.py         # pytest: config loading, defaults
```

Add to `pyproject.toml` or `pytest.ini`:
```ini
[tool.pytest.ini_options]
testpaths = ["tests", "scripts"]
python_files = ["test_*.py"]
```

Add to CI (`.github/workflows/ci.yml` or news-generate.yml):
```yaml
- name: Run Python tests
  run: pytest tests/ -v --tb=short
```

---

### 3. Add GitHub Actions CI Workflow for Python Tests

**Problem:** There is no CI workflow that runs Python tests on PRs or pushes to main. The `news-generate.yml` workflow only runs on schedule, not on code changes.

**Recommendation:** Add `.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
      - run: pip install feedparser PyYAML requests rapidfuzz pytest beautifulsoup4 tzdata python-dateutil
      - run: pytest tests/ scripts/test_dedup.py -v
      - run: python test_negative_keywords.py
      - run: python test_tagging_dashboard.py
```

---

### 4. Feed URL Allowlisting

**Problem:** `config.yaml` is the only guard against fetching arbitrary URLs. If config.yaml is ever modified by an untrusted party (e.g., a PR from an external contributor), fetch_news.py would follow any URL.

**Recommendation:** Add a domain allowlist check in `fetch_feed_entries()`:
```python
ALLOWED_SCHEMES = {"http", "https"}

def is_safe_feed_url(url: str) -> bool:
    """Reject non-HTTP/HTTPS feed URLs before fetching."""
    try:
        p = urlparse(url)
        return p.scheme in ALLOWED_SCHEMES and bool(p.netloc)
    except Exception:
        return False
```

This also prevents SSRF via `file://`, `ftp://`, or internal network URLs (`http://169.254.169.254/latest/meta-data/`).

---

### 5. Rate Limiting Awareness in scraper.py

**Problem:** `scraper.py` enforces a 2-second delay between requests to the *same scraper instance*, but multiple scrapers could still hammer the same domain in parallel if called concurrently.

**Recommendation:** Use a shared domain-level rate limiter (e.g., `threading.Lock` + timestamps per domain) or add a note in scraper base class that parallel scraping requires coordination.

---

### 6. Structured Logging Instead of print() Statements

**Problem:** The codebase mixes `logging.*` calls (correct) with bare `print()` in test scripts and some utility scripts. This makes it harder to filter log levels in production.

**Recommendation:** Replace all `print()` calls in `fetch_news.py` (particularly in the `ANSI color` console output paths) with `logging.info()`. Reserve `print()` for test scripts only.

---

### 7. Pin Dependency Versions

**Problem:** `requirements.txt` uses `>=` version constraints, meaning a dependency update could break the pipeline on the next scheduled run without a code change.

**Recommendation:** Generate and commit a `requirements.lock` or use `pip-compile` from `pip-tools`:
```bash
pip-compile requirements.txt -o requirements.lock
```
Use `requirements.lock` in production workflows and `requirements.txt` for development flexibility.

---

### 8. Consider Input Validation for Config YAML

**Problem:** Config values (e.g., `fuzz_threshold`, `max_per_domain`) are read from YAML with minimal validation. An invalid config (e.g., `fuzz_threshold: "not_a_float"`) would cause a runtime error mid-run.

**Recommendation:** Add a `validate_config()` function that checks types and ranges at startup, failing fast with a clear error message before any feeds are fetched.

---

## 📊 Current Test Coverage Summary

| Test | Type | Passes | Notes |
|------|------|--------|-------|
| `test_negative_keywords.py` | Integration | ✅ | Tests live config + module |
| `scripts/test_dedup.py` | Unit | ✅ | Tests URL extraction + filtering |
| `test_tagging_dashboard.py` | Integration | ✅ | All 4 checks pass after fix |
| `test_regex.py` | Smoke | ✅ | Validates post file format |
| Python syntax check (all .py) | Static | ✅ | All files parse correctly |

**Gap:** No tests for HTML escaping, URL sanitization, config loading, or the Astro/TypeScript frontend.

---

## 🔒 Security Summary

### Fixed in This Review
- **XSS via feed content** (5 locations): RSS feeds could inject HTML/JS into generated `.md` posts via malicious article titles, summaries, or source names. Fixed with `html.escape()`.
- **Mermaid XSS**: `securityLevel: 'loose'` allowed JS execution via diagram content. Changed to `'strict'`.
- **Error post injection**: `feed_url` and `error_message` written raw to Markdown files. Now HTML-entity-encoded.

### Residual / Accepted Risks
- **SSRF (Low)**: `fetch_feed_entries()` fetches URLs from config.yaml. Since config is in the repo, only repo collaborators can add URLs. Recommend adding an allowlist check for defense-in-depth.
- **Markdown injection in Markdown sections**: Titles in Markdown-formatted sections (e.g., `**{title}**`) could contain `*` or `_` that disrupts rendering but does not cause code execution. Lower severity since Markdown processors do not execute embedded content.
- **Gemini API key in config**: `config.yaml` has a `gemini.api_key` fallback field. If committed with a real key, it would be exposed in the repo. Always use `GEMINI_API_KEY` environment variable in production (already the default path).
