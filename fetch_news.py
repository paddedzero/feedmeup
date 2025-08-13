import feedparser
import yaml
import re
import socket
import requests
from datetime import datetime, timezone
from pathlib import Path

# --- ANSI color codes ---
RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
GREY = "\033[90m"

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
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = re.sub(r'[^a-z0-9]+', '-', f"feed-error-{date_str}").strip('-')
    filename = output_dir / f"{date_str}-{slug}.md"
    
    front_matter = f"""---
layout: post
title: "Feed Fetch Error - {date_str}"
date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S +0000')}
categories: error
---

"""
    content = f"**Failed to fetch feed:** {feed_url}\n\n**Error:** {error_message}\n"
    full_content = front_matter + content

    with open(filename, "w", encoding="utf-8") as f:
        f.write(full_content)

    print(f"[ERROR POST] Saved: {filename}")

def fetch_feed_entries(url, feed_name):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "").lower()
        if not ("xml" in content_type or "rss" in content_type):
            msg = f"Invalid content type: {content_type}"
            save_error_post(url, msg)
            return [], msg

        encoding = resp.encoding if resp.encoding else 'utf-8'
        content = resp.content.decode(encoding, errors='replace')

        feed = feedparser.parse(content)
        if feed.bozo:
            msg = f"Parse error: {feed.bozo_exception}"
            save_error_post(url, msg)
            return [], msg

        return feed.entries, "OK"

    except requests.exceptions.RequestException as e:
        msg = f"Network error: {e}"
        save_error_post(url, msg)
        return [], msg
    except Exception as e:
        msg = f"Unexpected error: {e}"
        save_error_post(url, msg)
        return [], msg

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

    print(f"[POST] Created: {filename}")

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
    summary = []

    for source in sources:
        feed_name = source.get("name", source["url"])
        url = source["url"]

        print(f"\n[FETCH] {feed_name}")
        entries, status = fetch_feed_entries(url, feed_name)

        if status != "OK":
            summary.append((feed_name, status, 0))
            continue

        matched_entries = [e for e in entries if entry_matches(e, pattern)]
        all_matched_entries.extend(matched_entries)
        summary.append((feed_name, "OK", len(matched_entries)))

    if not all_matched_entries:
        print("\n[INFO] No matching news found this run.")
    else:
        for entry in all_matched_entries:
            title, content = format_entry(entry)
            if "published_parsed" in entry and entry.published_parsed:
                date = datetime(*entry.published_parsed[:6])
            else:
                date = datetime.utcnow()
            save_post(title, date, content)

    # --- FEED-BY-FEED SUMMARY ---
    print("\n=== FEED SUMMARY ===")
    for name, status, count in summary:
        if status == "OK":
            status_color = GREEN + status + RESET
        else:
            status_color = RED + status + RESET

        if count > 0:
            count_color = YELLOW + str(count) + RESET
        else:
            count_color = GREY + str(count) + RESET

        print(f"{name:40} | Status: {status_color:25} | Matches: {count_color}")
    print("====================\n")

if __name__ == "__main__":
    main()
