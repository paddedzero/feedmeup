import feedparser
import yaml
import re
from datetime import datetime
from pathlib import Path

CONFIG_FILE = "config.yaml"
POSTS_DIR = Path("_posts")

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def compile_keywords_pattern(keywords):
    escaped = [re.escape(k) for k in keywords]
    pattern = r"(?i)\b(" + "|".join(escaped) + r")\b"
    return re.compile(pattern)

def fetch_feed_entries(url):
    feed = feedparser.parse(url)
    if feed.bozo:
        print(f"Warning: Failed to parse feed {url}")
    return feed.entries

def entry_matches(entry, pattern):
    text_to_check = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
    return bool(pattern.search(text_to_check))

def format_entries_for_category(entries):
    formatted = []
    for entry in entries:
        title = entry.get("title", "No Title")
        link = entry.get("link", "")
        summary = entry.get("summary", "No summary available").strip().replace('\n', ' ')
        formatted.append(f"- **{title}** — {summary}\n  [Read more]({link})")
    return "\n\n".join(formatted)

def create_post_file(date_str, content_by_category):
    POSTS_DIR.mkdir(exist_ok=True)
    filename = POSTS_DIR / f"{date_str}-news-brief.md"

    front_matter = f"""---
layout: post
title: "Weekly AI & Security Brief — {date_str}"
date: {date_str}
categories: news brief
---

"""

    body = f"# Weekly AI & Security Brief — {date_str}\n\n"
    for category in sorted(content_by_category.keys()):
        body += f"## {category}\n\n"
        body += content_by_category[category] + "\n\n"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(front_matter)
        f.write(body)
    print(f"Created Jekyll post: {filename}")

def main():
    config = load_config()
    keywords = config.get("filters", {}).get("keywords", [])
    sources = config.get("sources", [])
    pattern = compile_keywords_pattern(keywords)

    reports = {}
    for source in sources:
        entries = fetch_feed_entries(source["url"])
        matched_entries = [e for e in entries if entry_matches(e, pattern)]
        if matched_entries:
            cat = source.get("category", "General")
            if cat not in reports:
                reports[cat] = []
            reports[cat].extend(matched_entries)

    if not reports:
        print("No matching news found this run.")
        return

    today = datetime.utcnow().strftime("%Y-%m-%d")
    content_by_category = {}
    for cat, entries in reports.items():
        content_by_category[cat] = format_entries_for_category(entries)

    create_post_file(today, content_by_category)

if __name__ == "__main__":
    main()
# fetch_news.py