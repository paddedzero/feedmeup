import feedparser
import yaml
import re
import socket
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

def save_error_post(feed_url, error_message, output_dir=POSTS_DIR):
    output_dir.mkdir(exist_ok=True)
    date_str = datetime.utcnow().strftime('%Y-%m-%d')
    slug = re.sub(r'[^a-z0-9]+', '-', f"feed-error-{date_str}").strip('-')
    filename = output_dir / f"{date_str}-{slug}.md"
    
    front_matter = f"""---
layout: post
title: "Feed Fetch Error - {date_str}"
date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S +0000')}
categories: error
---

"""

    content = f"**Failed to fetch feed:** {feed_url}\n\n**Error:** {error_message}\n"
    full_content = front_matter + content

    with open(filename, "w", encoding="utf-8") as f:
        f.write(full_content)

    print(f"Created error post: {filename}")

def fetch_feed_entries(url):
    try:
        feed = feedparser.parse(url)
        if feed.bozo:
            print(f"Warning: Failed to parse feed {url}")
        return feed.entries
    except (ConnectionResetError, socket.error, Exception) as e:
        print(f"Warning: Exception while fetching {url}: {e}")
        save_error_post(url, str(e))
        return []
    
def entry_matches(entry, pattern):
    text_to_check = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
    return bool(pattern.search(text_to_check))

def save_post(title, date, content, output_dir=POSTS_DIR):
    output_dir.mkdir(exist_ok=True)
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    date_str = date.strftime('%Y-%m-%d')
    datetime_str = date.strftime('%Y-%m-%d %H:%M:%S %z') or date.strftime('%Y-%m-%d %H:%M:%S +0000')
    filename = output_dir / f"{date_str}-{slug}.md"

    front_matter = f"""---
layout: post
title: "{title}"
date: {datetime_str}
categories: news brief
---

"""

    full_content = front_matter + content

    with open(filename, "w", encoding="utf-8") as f:
        f.write(full_content)

    print(f"Created Jekyll post: {filename}")

def format_entry(entry):
    title = entry.get("title", "No Title")
    link = entry.get("link", "")
    summary = entry.get("summary", "No summary available").strip().replace('\n', ' ')
    content = f"{summary}\n\n[Read more]({link})"
    return title, content

def main():
    config = load_config()
    keywords = config.get("filters", {}).get("keywords", [])
    sources = config.get("sources", [])
    pattern = compile_keywords_pattern(keywords)

    all_matched_entries = []

    for source in sources:
        entries = fetch_feed_entries(source["url"])
        matched_entries = [e for e in entries if entry_matches(e, pattern)]
        all_matched_entries.extend(matched_entries)

    if not all_matched_entries:
        print("No matching news found this run.")
        return

    for entry in all_matched_entries:
        title, content = format_entry(entry)
        # Use published_parsed or fallback to current time
        if "published_parsed" in entry and entry.published_parsed:
            date = datetime(*entry.published_parsed[:6])
        else:
            date = datetime.utcnow()
        save_post(title, date, content)

if __name__ == "__main__":
    main()
# fetch_news.py
# This script fetches news from configured sources, filters them by keywords,