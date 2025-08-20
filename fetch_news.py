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

def format_entries_for_category(entries):
    """Format entries as markdown for a category, newest first."""
    def get_pub_date(entry):
        if "published_parsed" in entry and entry.published_parsed:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return datetime.now(timezone.utc)
    
    sorted_entries = sorted(entries, key=get_pub_date, reverse=True)
    formatted = []
    for entry in sorted_entries:
        title = entry.get("title", "No Title")
        link = entry.get("link", "")
        summary = entry.get("summary", "No summary available").strip().replace('\n', ' ')
        if len(summary) > 200:
            summary = summary[:197] + "..."
        formatted.append(f"- **{title}** — {summary}\n  [Read more]({link})")
    return "\n\n".join(formatted)

# def create_news_brief(date_str, content_by_category, highlights):
#     """Create a single news brief post instead of individual posts"""
#     POSTS_DIR.mkdir(exist_ok=True)
#     filename = POSTS_DIR / f"{date_str}-news-brief.md"

#     front_matter = f"""---
# layout: post
# title: "Weekly News Brief — {date_str}"
# date: {date_str} 12:00:00 +0000
# categories: [newsbrief]
# ---

# """

#     # Top 5 highlights section
#     highlights_section = "## Top 5 Highlights\n\n"
#     for i, (title, count) in enumerate(highlights, start=1):
#         highlights_section += f"{i}. {title} ({count} mentions)\n"
#     highlights_section += "\n"

#     # Generate summary table
#     table = "| Category | Articles |\n|---|---|\n"
#     total_articles = 0
#     for category, entries in sorted(content_by_category.items()):
#         article_count = len([line for line in entries.split('\n') if line.strip().startswith('- **')])
#         table += f"| {category} | {article_count} |\n"
#         total_articles += article_count

#     body = f"# Weekly News Brief — {date_str}\n\n"
#     body += highlights_section
#     body += "## Summary\n\n"
#     body += table + f"\n**Total Articles: {total_articles}**\n\n"

#     for category in sorted(content_by_category.keys()):
#         body += f"## {category}\n\n"
#         body += content_by_category[category] + "\n\n"

#     with open(filename, "w", encoding="utf-8") as f:
#         f.write(front_matter + body)
#     print(f"{GREEN}[NEWS BRIEF]{RESET} Created: {filename}")

def create_news_brief(date_str, content_by_category, highlights):
    """Create a single news brief post with Top 10 highlights."""
    POSTS_DIR.mkdir(exist_ok=True)
    filename = POSTS_DIR / f"{date_str}-news-brief.md"

    # --- NEW: Create the formatted date for the title ---
    date_object = datetime.strptime(date_str, "%Y-%m-%d")
    formatted_title_date = date_object.strftime("%b %d, %Y")
    # --- END NEW SECTION ---

    front_matter = f"""---
layout: post
title: "Weekly News Brief on Cloud, Cybersecurity, AI, ML — {formatted_title_date}"
date: {date_str} 12:00:00 +0000
categories: [newsbrief]
---

"""
    # --- NEW: Top 10 highlights section ---
    highlights_section = "## Top 10 Highlights\n\n"
    for i, (entry, count) in enumerate(highlights, start=1):
        title = entry.get("title", "No Title")
        link = entry.get("link", "#")
        # Clean up and shorten the summary
        summary = entry.get("summary", "No summary available.").strip().replace('\n', ' ')
        if len(summary) > 250:
            summary = summary[:247] + "..."
        
        highlights_section += f"{i}. **{title}** ({count} mentions)\n"
        highlights_section += f"   > {summary}\n"
        highlights_section += f"   > [Read more]({link})\n\n"
    # --- END NEW SECTION ---

    # Generate summary table
    table = "| Category | Articles |\n|---|---|\n"
    total_articles = 0
    for category, entries_text in sorted(content_by_category.items()):
        article_count = len([line for line in entries_text.split('\n') if line.strip().startswith('- **')])
        table += f"| {category} | {article_count} |\n"
        total_articles += article_count

    # body = f"# Weekly News Brief — {date_str}\n\n"
    body = highlights_section
    body += "## Summary\n\n"
    body += table + f"\n**Total Articles: {total_articles}**\n\n"

    for category in sorted(content_by_category.keys()):
        body += f"## {category}\n\n"
        body += content_by_category[category] + "\n\n"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(front_matter + body)
    print(f"{GREEN}[NEWS BRIEF]{RESET} Created: {filename}")

# def group_similar_titles(titles, threshold=FUZZ_THRESHOLD):
#     """Group titles that are similar using fuzzy matching."""
#     grouped = []
#     used = set()

#     for i, t1 in enumerate(titles):
#         if i in used:
#             continue
#         group_count = 1
#         for j, t2 in enumerate(titles[i+1:], start=i+1):
#             if j in used:
#                 continue
#             if SequenceMatcher(None, t1.lower(), t2.lower()).ratio() >= threshold:
#                 group_count += 1
#                 used.add(j)
#         grouped.append((t1, group_count))
#     # Sort descending by count
#     grouped.sort(key=lambda x: x[1], reverse=True)
#     return grouped[:5]

def group_similar_entries(entries, threshold=FUZZ_THRESHOLD):
    """Group entries that are similar using fuzzy title matching."""
    grouped = []
    used_indices = set()

    for i, entry1 in enumerate(entries):
        if i in used_indices:
            continue
        
        group_count = 1
        # Find similar entries
        for j, entry2 in enumerate(entries[i+1:], start=i+1):
            if j in used_indices:
                continue
            
            title1 = entry1.get("title", "").lower()
            title2 = entry2.get("title", "").lower()
            
            if SequenceMatcher(None, title1, title2).ratio() >= threshold:
                group_count += 1
                used_indices.add(j)
        
        # Store the original entry and its mention count
        grouped.append((entry1, group_count))
        used_indices.add(i)

    # Sort descending by count
    grouped.sort(key=lambda x: x[1], reverse=True)
    # Return the top 10
    return grouped[:10]

def main():
    print(f"{YELLOW}Starting news aggregation...{RESET}\n")
    
    config = load_config()
    keywords = config.get("filters", {}).get("keywords", [])
    sources = config.get("sources", [])
    pattern = compile_keywords_pattern(keywords)

    print(f"{GREY}Configuration loaded:{RESET}")
    print(f"{GREY}  - Sources: {len(sources)}{RESET}")
    print(f"{GREY}  - Keywords: {keywords}{RESET}")
    
    reports = {}
    # all_titles = []
    all_matched_entries = []
    errors = 0
    total_entries = 0
    recent_entries = 0
    matched_entries = 0
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)

    print(f"{GREY}  - Looking for entries after: {cutoff_date.strftime('%Y-%m-%d')}{RESET}\n")

    for i, source in enumerate(sources, 1):
        feed_name = source.get("name", source["url"])
        url = source["url"]
        category = source.get("category", "General")

        print(f"[{i}/{len(sources)}] {feed_name}")
        entries, status = fetch_feed_entries(url, feed_name)

        if status != "OK":
            errors += 1
            print(f"{RED}  ✗ Failed: {status}{RESET}")
            continue

        print(f"{GREEN}  ✓ Found {len(entries)} total entries{RESET}")
        total_entries += len(entries)
        
        recent_count = 0
        matched_count = 0
        
        for entry in entries:
            pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc) if "published_parsed" in entry and entry.published_parsed else datetime.now(timezone.utc)
            
            if pub_date >= cutoff_date:
                recent_count += 1
                recent_entries += 1
                
                if entry_matches(entry, pattern):
                    matched_count += 1
                    matched_entries += 1
                    if category not in reports:
                        reports[category] = []
                    reports[category].append(entry)
                    # all_titles.append(entry.get("title", "No Title"))
                    all_matched_entries.append(entry) # <-- Store the whole entry
        
        print(f"{GREY}    Recent: {recent_count}, Matched: {matched_count}{RESET}")

    # Debug summary
    print(f"\n{'='*50}")
    print(f"{YELLOW}PROCESSING SUMMARY{RESET}")
    print(f"{'='*50}")
    print(f"Total entries found: {total_entries}")
    print(f"Recent entries (last 30 days): {recent_entries}")
    print(f"Entries matching keywords: {matched_entries}")
    print(f"Feed errors: {errors}/{len(sources)}")
    print(f"Categories found: {list(reports.keys()) if reports else 'None'}")

    if not reports:
        print(f"\n{RED}[NO RESULTS]{RESET} No matching news found!")
        print(f"{YELLOW}Possible issues:{RESET}")
        if errors == len(sources):
            print(f"  - All feeds failed to load")
        elif recent_entries == 0:
            print(f"  - No articles published in last 30 days")
        elif matched_entries == 0:
            print(f"  - No articles matched keywords: {keywords}")
            print(f"  - Try broader keywords or check spelling")
        return

    # Create news brief
    # top_highlights = group_similar_titles(all_titles)
    top_highlights = group_similar_entries(all_matched_entries)
    
    #today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Use yesterday's date to avoid all future-dating issues with UTC.
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    today = yesterday.strftime("%Y-%m-%d")
    content_by_category = {}
    
    for cat, entries in reports.items():
        content_by_category[cat] = format_entries_for_category(entries)

    create_news_brief(today, content_by_category, top_highlights)
    
    print(f"\n{GREEN}[SUCCESS]{RESET} News brief generated with {matched_entries} articles across {len(reports)} categories")

if __name__ == "__main__":
    main()