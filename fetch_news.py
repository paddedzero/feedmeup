import feedparser
import yaml
import re
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher

# --- ANSI color codes ---
RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
GREY = "\033[90m"

CONFIG_FILE = "config.yaml"
POSTS_DIR = Path("_posts")
ERRORS_DIR = Path("_errors")

FUZZ_THRESHOLD = 0.8  # 80% similarity to consider titles the same

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def compile_keywords_pattern(keywords):
    escaped = [re.escape(k) for k in keywords]
    pattern = r"(?i)\b(" + "|".join(escaped) + r")\b"
    return re.compile(pattern)

def save_error_post(feed_url, error_message):
    try:
        ERRORS_DIR.mkdir(exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        slug = re.sub(r'[^a-z0-9]+', '-', f"feed-error-{date_str}").strip('-')
        filename = ERRORS_DIR / f"{date_str}-{slug}.md"
        front_matter = f"""---
layout: post
title: "Feed Fetch Error - {date_str}"
date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S +0000')}
categories: error
---

"""
        content = f"**Failed to fetch feed:** {feed_url}\n\n**Error:** {error_message}\n"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(front_matter + content)
        print(f"{RED}[ERROR POST]{RESET} Saved to {filename}")
    except Exception as e:
        print(f"{RED}[ERROR]{RESET} Failed to save error post: {e}")

def fetch_feed_entries(url, feed_name):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; RSS-Bot/1.0)'}
        resp = requests.get(url, timeout=15, headers=headers)

        if resp.status_code in [403, 404]:
            msg = f"HTTP {resp.status_code} error"
            save_error_post(url, msg)
            return [], msg
        
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "").lower()
        if not any(x in content_type for x in ["xml", "rss", "atom"]):
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

def format_entries_for_category(entries):
    """Format entries as markdown for a category, newest first."""
    def get_pub_date(entry):
        if "published_parsed" in entry and entry.published_parsed:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return datetime.utcnow()
    
    sorted_entries = sorted(entries, key=get_pub_date, reverse=True)
    formatted = []
    for entry in sorted_entries:
        title = entry.get("title", "No Title")
        link = entry.get("link", "")
        summary = entry.get("summary", "No summary available").strip().replace('\n', ' ')
        formatted.append(f"- **{title}** — {summary}\n  [Read more]({link})")
    return "\n\n".join(formatted)

def create_news_brief(date_str, content_by_category, highlights):
    POSTS_DIR.mkdir(exist_ok=True)
    filename = POSTS_DIR / f"{date_str}-news-brief.md"

    front_matter = f"""---
layout: post
title: "Weekly News Brief — {date_str}"
date: {date_str}
categories: news brief
---

"""

    # Top 5 highlights section
    highlights_section = "## Top 5 Highlights\n\n"
    for i, (title, count) in enumerate(highlights, start=1):
        highlights_section += f"{i}. {title} ({count} mentions)\n"
    highlights_section += "\n"

    # Generate summary table
    table = "| Category | Articles |\n|---|---|\n"
    for category, entries in sorted(content_by_category.items()):
        table += f"| {category} | {len(entries.splitlines())} |\n"

    body = f"# Weekly News Brief — {date_str}\n\n"
    body += highlights_section
    body += "## Summary\n\n"
    body += table + "\n\n"

    for category in sorted(content_by_category.keys()):
        body += f"## {category}\n\n"
        body += content_by_category[category] + "\n\n"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(front_matter + body)
    print(f"{GREEN}[POST]{RESET} Created Jekyll post: {filename}")

def group_similar_titles(titles, threshold=FUZZ_THRESHOLD):
    """Group titles that are similar using fuzzy matching."""
    grouped = []
    used = set()

    for i, t1 in enumerate(titles):
        if i in used:
            continue
        group_count = 1
        for j, t2 in enumerate(titles[i+1:], start=i+1):
            if j in used:
                continue
            if SequenceMatcher(None, t1.lower(), t2.lower()).ratio() >= threshold:
                group_count += 1
                used.add(j)
        grouped.append((t1, group_count))
    # Sort descending by count
    grouped.sort(key=lambda x: x[1], reverse=True)
    return grouped[:5]

def main():
    config = load_config()
    keywords = config.get("filters", {}).get("keywords", [])
    sources = config.get("sources", [])
    pattern = compile_keywords_pattern(keywords)

    reports = {}
    all_titles = []
    errors = 0
    cutoff_date = datetime.utcnow() - timedelta(days=30)

    for source in sources:
        feed_name = source.get("name", source["url"])
        url = source["url"]
        print(f"\n[FETCH] {feed_name}")

        entries, status = fetch_feed_entries(url, feed_name)
        if status != "OK":
            errors += 1
            continue

        for entry in entries:
            pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc) if "published_parsed" in entry else datetime.utcnow()
            if pub_date >= cutoff_date and entry_matches(entry, pattern):
                cat = source.get("category", "General")
                if cat not in reports:
                    reports[cat] = []
                reports[cat].append(entry)
                all_titles.append(entry.get("title", "No Title"))

    if not reports:
        print(f"{YELLOW}[INFO]{RESET} No matching news found in the last 30 days.")
        return

    # Compute top 5 fuzzy-matched highlights
    top_highlights = group_similar_titles(all_titles)

    today = datetime.utcnow().strftime("%Y-%m-%d")
    content_by_category = {}
    for cat, entries in reports.items():
        content_by_category[cat] = format_entries_for_category(entries)

    create_news_brief(today, content_by_category, top_highlights)

if __name__ == "__main__":
    main()
