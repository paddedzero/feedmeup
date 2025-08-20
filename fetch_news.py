import feedparser
import yaml
import re
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from requests.utils import requote_uri
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup      # new import

# rapidfuzz for fuzzy matching
from rapidfuzz.fuzz import ratio as rf_ratio

# requests retry
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- ANSI color codes (kept for console output) ---
RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
GREY = "\033[90m"

CONFIG_FILE = "config.yaml"
POSTS_DIR = Path("_posts")
ERRORS_DIR = Path("_errors")

# Use America/New_York as the local timezone
LOCAL_TZ = ZoneInfo("America/New_York")

# Defaults (can be overridden by config.yaml)
DEFAULTS = {
    "fuzz_threshold": 0.8,
    "max_per_domain": 2,
    "max_results": 10,
    "request_retries": 3,
    "request_backoff": 0.3,
    "request_timeout": 15,
    "request_status_forcelist": [429, 500, 502, 503, 504],
    "log_level": "INFO",
}

# Module-level session (initialized in main)
SESSION = None


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logging.warning("config.yaml not found, using defaults")
        return {}
    except Exception:
        logging.exception("Failed to load config.yaml; using defaults")
        return {}


def compile_keywords_pattern(keywords):
    if not keywords:
        return re.compile(r"$^")  # never matches
    escaped = [re.escape(k) for k in keywords]
    pattern = r"(?i)\b(" + "|".join(escaped) + r")\b"
    return re.compile(pattern)


def save_error_post(feed_url, error_message):
    """Save feed fetch error into _errors folder instead of _posts."""
    try:
        ERRORS_DIR.mkdir(exist_ok=True)
        now_local = datetime.now(LOCAL_TZ)
        date_str = now_local.strftime("%Y-%m-%d")
        slug = re.sub(r'[^a-z0-9]+', '-', f"feed-error-{date_str}").strip('-')
        filename = ERRORS_DIR / f"{date_str}-{slug}.md"

        front_matter = f"""---
layout: post
title: "Feed Fetch Error - {date_str}"
date: {now_local.strftime('%Y-%m-%d %H:%M:%S %z')}
categories: error
---

"""
        content = f"**Failed to fetch feed:** {feed_url}\n\n**Error:** {error_message}\n"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(front_matter + content)
        logging.error("[ERROR POST] Saved to %s", filename)
    except Exception:
        logging.exception("Failed to write error post")


def init_requests_session(retries=None, backoff=None, timeout=None, status_forcelist=None):
    """Initialize requests.Session with retry adapter and store globally."""
    global SESSION
    r = int(retries) if retries is not None else DEFAULTS["request_retries"]
    b = float(backoff) if backoff is not None else DEFAULTS["request_backoff"]
    status_list = status_forcelist if status_forcelist is not None else DEFAULTS["request_status_forcelist"]

    session = requests.Session()
    retry = Retry(
        total=r,
        backoff_factor=b,
        status_forcelist=list(status_list),
        allowed_methods=frozenset(["GET", "POST", "HEAD", "OPTIONS"])
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    SESSION = session
    return session


def fetch_feed_entries(url, feed_name):
    """Fetch feed content using the shared session (with retries)."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; RSS-Bot/1.0)'}
        timeout = DEFAULTS["request_timeout"]
        if SESSION:
            resp = SESSION.get(url, timeout=timeout, headers=headers)
        else:
            resp = requests.get(url, timeout=timeout, headers=headers)

        if resp.status_code in [403, 404]:
            msg = f"HTTP {resp.status_code} error"
            save_error_post(url, msg)
            return [], msg

        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "").lower()
        if content_type and not any(x in content_type for x in ["xml", "rss", "atom"]):
            msg = f"Invalid content type: {content_type}"
            save_error_post(url, msg)
            return [], msg

        feed = feedparser.parse(resp.content)
        if feed.bozo and not feed.entries:
            msg = f"Parse error: {feed.bozo_exception}"
            save_error_post(url, msg)
            return [], msg

        return feed.entries, "OK"

    except Exception as e:
        msg = str(e)
        save_error_post(url, msg)
        return [], msg


def entry_matches(entry, pattern):
    text_to_check = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
    return bool(pattern.search(text_to_check))


def clean_summary(html):
    """Return plaintext summary extracted from HTML; collapse whitespace."""
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        # collapse repeated whitespace
        return " ".join(text.split())
    except Exception:
        # fallback: strip tags crudely
        return " ".join(re.sub(r"<[^>]+>", " ", str(html)).split())


def sanitize_url(url):
    """Return a safe, percent-encoded URL or None if invalid."""
    try:
        if not url or not isinstance(url, str):
            return None
        u = url.strip()
        if not u:
            return None
        # percent-encode problematic chars
        safe = requote_uri(u)
        p = urlparse(safe)
        if not p.scheme or not p.netloc:
            return None
        return safe
    except Exception:
        return None


def format_entries_for_category(entries):
    """Format entries as markdown for a category, newest first."""
    def get_pub_date(entry):
        if "published_parsed" in entry and entry.published_parsed:
            return datetime(*entry.published_parsed[:6], tzinfo=LOCAL_TZ)
        return datetime.now(LOCAL_TZ)

    sorted_entries = sorted(entries, key=get_pub_date, reverse=True)
    formatted = []
    for entry in sorted_entries:
        title = entry.get("title", "No Title")
        link = entry.get("link", "")
        raw_summary = entry.get("summary", "") or entry.get("description", "")
        summary = clean_summary(raw_summary)
        if len(summary) > 200:
            summary = summary[:197] + "..."
        safe_link = sanitize_url(link)
        if safe_link:
            # use an explicit HTML anchor to avoid markdown processor mangling feed HTML
            formatted.append(f"- **{title}** — {summary}\n  <a href=\"{safe_link}\">Read more</a>")
        else:
            formatted.append(f"- **{title}** — {summary}")
    return "\n\n".join(formatted)


def create_news_brief(date_str, content_by_category, highlights):
    """Create a single news brief post with Top highlights.

    Filename includes local HH-MM to avoid collisions and include time.
    """
    POSTS_DIR.mkdir(exist_ok=True)

    now_local = datetime.now(LOCAL_TZ)
    time_filename = now_local.strftime("%H-%M")        # e.g. "13-45" (safe for filenames)
    filename = POSTS_DIR / f"{date_str}-{time_filename}-news-brief.md"

    date_object = datetime.strptime(date_str, "%Y-%m-%d")
    formatted_title_date = date_object.strftime("%b %d, %Y")
    time_front = now_local.strftime("%H:%M:%S %z")       # includes offset, e.g. -0400

    # use the same calendar date (date_str) for front-matter while keeping time format unchanged
    front_matter = f"""---
layout: post
title: "Weekly News Brief on Cloud, Cybersecurity, AI, ML — {formatted_title_date}"
date: {date_str} {time_front}
categories: [newsbrief]
---
"""

    highlights_section = "## Top Highlights\n\n"
    for i, (entry, count) in enumerate(highlights, start=1):
        title = entry.get("title", "No Title")
        link = entry.get("link", "#")
        summary = entry.get("summary", "No summary available.").strip().replace('\n', ' ')
        if len(summary) > 250:
            summary = summary[:247] + "..."

        safe_link = None
        try:
            safe_link = requote_uri(link.strip()) if link and isinstance(link, str) and link.strip() else None
        except Exception:
            safe_link = None

        summary = clean_summary(entry.get("summary", "") or entry.get("description", ""))
        if len(summary) > 250:
            summary = summary[:247] + "..."

        safe_link = sanitize_url(entry.get("link", ""))
        highlights_section += f"{i}. **{title}** ({count} mentions)\n"
        highlights_section += f"   > {summary}\n"
        if safe_link:
            highlights_section += f"   > <a href=\"{safe_link}\">Read more</a>\n\n"
        else:
            highlights_section += f"   > Read more (link omitted)\n\n"

    table = "| Category | Articles |\n|---|---|\n"
    total_articles = 0
    for category, entries_text in sorted(content_by_category.items()):
        article_count = len([line for line in entries_text.split('\n') if line.strip().startswith('- **')])
        table += f"| {category} | {article_count} |\n"
        total_articles += article_count

    body = highlights_section
    body += "## Summary\n\n"
    body += table + f"\n**Total Articles: {total_articles}**\n\n"

    for category in sorted(content_by_category.keys()):
        body += f"## {category}\n\n"
        body += content_by_category[category] + "\n\n"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(front_matter + body)
    logging.info("[NEWS BRIEF] Created: %s", filename)


def group_similar_entries(entries, threshold=None, max_per_domain=None, max_results=None):
    """Group entries by fuzzy title similarity, choose recent representative,
    sort by group size then recency, and diversify by normalized domain.

    Returns list of (entry, count) tuples up to max_results.
    """
    if not entries:
        return []

    fuzz_threshold = float(threshold) if threshold is not None else DEFAULTS["fuzz_threshold"]
    max_per_domain = int(max_per_domain) if max_per_domain is not None else DEFAULTS["max_per_domain"]
    max_results = int(max_results) if max_results is not None else DEFAULTS["max_results"]

    pre = []
    for idx, e in enumerate(entries):
        title = (e.get("title") or "").strip()
        title_l = title.lower()
        try:
            if "published_parsed" in e and e.published_parsed:
                pub = datetime(*e.published_parsed[:6], tzinfo=LOCAL_TZ)
            else:
                pub = datetime.now(LOCAL_TZ)
        except Exception:
            pub = datetime.now(LOCAL_TZ)
        pre.append({"idx": idx, "entry": e, "title_l": title_l, "pub": pub})

    grouped = []
    used = set()

    for i, item in enumerate(pre):
        if item["idx"] in used:
            continue

        group_indices = [item["idx"]]
        for other in pre[i+1:]:
            if other["idx"] in used:
                continue
            score = rf_ratio(item["title_l"], other["title_l"]) / 100.0
            if score >= fuzz_threshold:
                group_indices.append(other["idx"])
                used.add(other["idx"])

        used.add(item["idx"])
        group_items = [x for x in pre if x["idx"] in group_indices]
        rep = max(group_items, key=lambda x: x["pub"]) if group_items else item
        grouped.append({"rep": rep["entry"], "count": len(group_indices), "pub": rep["pub"]})

    # Sort by count desc then pub desc
    grouped.sort(key=lambda g: (g["count"], g["pub"]), reverse=True)

    def normalize_domain(link):
        try:
            net = urlparse(link).netloc.lower().split(":")[0]
            if net.startswith("www."):
                net = net[4:]
            return net
        except Exception:
            return ""

    diversified = []
    seen_domains = {}
    for g in grouped:
        if len(diversified) >= max_results:
            break
        entry = g["rep"]
        count = g["count"]
        link = (entry.get("link") or "").strip()
        if not link:
            continue
        domain = normalize_domain(link) or "__unknown__"
        if seen_domains.get(domain, 0) < max_per_domain:
            diversified.append((entry, count))
            seen_domains[domain] = seen_domains.get(domain, 0) + 1

    return diversified


def main():
    config = load_config()
    log_level = config.get("log_level", DEFAULTS["log_level"]).upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO), format="%(levelname)s: %(message)s")

    init_requests_session(
        retries=config.get("request_retries", DEFAULTS["request_retries"]),
        backoff=config.get("request_backoff", DEFAULTS["request_backoff"]),
        timeout=config.get("request_timeout", DEFAULTS["request_timeout"]),
        status_forcelist=config.get("request_status_forcelist", DEFAULTS["request_status_forcelist"]),
    )

    logging.info("%s Starting news aggregation... %s", YELLOW, RESET)

    keywords = config.get("filters", {}).get("keywords", [])
    sources = config.get("sources", [])
    pattern = compile_keywords_pattern(keywords)

    logging.info("Configuration: sources=%d, keywords=%s", len(sources), keywords)

    reports = {}
    all_matched_entries = []
    errors = 0
    total_entries = 0
    recent_entries = 0
    matched_entries = 0
    cutoff_date = datetime.now(LOCAL_TZ) - timedelta(days=30)

    logging.debug("Looking for entries after: %s", cutoff_date.strftime('%Y-%m-%d'))

    for i, source in enumerate(sources, 1):
        feed_name = source.get("name", source.get("url"))
        url = source.get("url")
        category = source.get("category", "General")

        logging.info("[%d/%d] %s", i, len(sources), feed_name)
        entries, status = fetch_feed_entries(url, feed_name)

        if status != "OK":
            errors += 1
            logging.warning("  ✗ Failed: %s", status)
            continue

        logging.info("  ✓ Found %d total entries", len(entries))
        total_entries += len(entries)

        recent_count = 0
        matched_count = 0

        for entry in entries:
            pub_date = datetime(*entry.published_parsed[:6], tzinfo=LOCAL_TZ) if "published_parsed" in entry and entry.published_parsed else datetime.now(LOCAL_TZ)

            if pub_date >= cutoff_date:
                recent_count += 1
                recent_entries += 1

                if entry_matches(entry, pattern):
                    matched_count += 1
                    matched_entries += 1
                    reports.setdefault(category, []).append(entry)
                    all_matched_entries.append(entry)

        logging.debug("    Recent: %d, Matched: %d", recent_count, matched_count)

    logging.info("PROCESSING SUMMARY")
    logging.info("Total entries found: %d", total_entries)
    logging.info("Recent entries (last 30 days): %d", recent_entries)
    logging.info("Entries matching keywords: %d", matched_entries)
    logging.info("Feed errors: %d/%d", errors, len(sources))
    logging.info("Categories found: %s", list(reports.keys()) if reports else 'None')

    if not reports:
        logging.warning("No matching news found")
        if errors == len(sources):
            logging.warning("  - All feeds failed to load")
        elif recent_entries == 0:
            logging.warning("  - No articles published in last 30 days")
        elif matched_entries == 0:
            logging.warning("  - No articles matched keywords; try broader keywords")
        return

    fuzz_threshold = config.get("fuzz_threshold", DEFAULTS["fuzz_threshold"])
    max_per_domain = config.get("max_per_domain", DEFAULTS["max_per_domain"])
    max_results = config.get("max_results", DEFAULTS["max_results"])

    top_highlights = group_similar_entries(all_matched_entries, threshold=fuzz_threshold, max_per_domain=max_per_domain, max_results=max_results)

    now_local = datetime.now(LOCAL_TZ)
    yesterday = now_local - timedelta(days=1)
    today = yesterday.strftime("%Y-%m-%d")
    content_by_category = {}

    for cat, entries in reports.items():
        content_by_category[cat] = format_entries_for_category(entries)

    create_news_brief(today, content_by_category, top_highlights)

    logging.info("%s News brief generated with %d articles across %d categories", GREEN, matched_entries, len(reports))


if __name__ == "__main__":
    main()