import feedparser
import yaml
import re
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
ERRORS_DIR = Path("_errors")

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def compile_keywords_pattern(keywords):
    escaped = [re.escape(k) for k in keywords]
    pattern = r"(?i)\b(" + "|".join(escaped) + r")\b"
    return re.compile(pattern)

def save_error_post(feed_url, error_message):
    """Save feed fetch error into _errors folder instead of _posts."""
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
    except:
        pass  # Don't let error saving crash the main process

def fetch_feed_entries(url, feed_name):
    try:
        # Add headers to avoid blocks and increase timeout
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; RSS-Bot/1.0)'}
        resp = requests.get(url, timeout=15, headers=headers)
        
        # Handle common HTTP errors
        if resp.status_code in [403, 404]:
            msg = f"HTTP {resp.status_code} error"
            save_error_post(url, msg)
            return [], msg
            
        resp.raise_for_status()
        
        # Check content type
        content_type = resp.headers.get("Content-Type", "").lower()
        if not any(x in content_type for x in ["xml", "rss", "atom"]):
            msg = f"Invalid content type: {content_type}"
            save_error_post(url, msg)
            return [], msg

        # Parse feed
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

def save_post(title, date, content):
    POSTS_DIR.mkdir(exist_ok=True)
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    date_str = date.strftime('%Y-%m-%d')
    datetime_str = date.strftime('%Y-%m-%d %H:%M:%S %z') or date.strftime('%Y-%m-%d %H:%M:%S +0000')
    filename = POSTS_DIR / f"{date_str}-{slug}.md"

    front_matter = f"""---
layout: post
title: "{title}"
date: {datetime_str}
categories: news brief
---

"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(front_matter + content)

    print(f"{GREEN}[POST]{RESET} Created: {filename}")

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
    errors = 0

    for source in sources:
        feed_name = source.get("name", source["url"])
        url = source["url"]

        print(f"\n[FETCH] {feed_name}")
        entries, status = fetch_feed_entries(url, feed_name)

        if status != "OK":
            summary.append((feed_name, status, 0))
            errors += 1
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

    # Print summary
    print("\n=== FEED SUMMARY ===")
    for name, status, count in summary:
        status_color = GREEN + status + RESET if status == "OK" else RED + status + RESET
        count_color = YELLOW + str(count) + RESET if count > 0 else GREY + str(count) + RESET
        print(f"{name:40} | Status: {status_color:25} | Matches: {count_color}")
    
    print(f"\nErrors: {errors}/{len(sources)}")
    
    # Only exit with error if ALL feeds failed
    if errors == len(sources) and len(sources) > 0:
        exit(1)

if __name__ == "__main__":
    main()