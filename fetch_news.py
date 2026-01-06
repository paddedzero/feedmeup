import feedparser
import yaml
import re
import requests
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from requests.utils import requote_uri
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

# rapidfuzz for fuzzy matching
from rapidfuzz.fuzz import ratio as rf_ratio

# requests retry
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Gemini API for summarization (Phase 1) - using new google-genai SDK
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("google-genai not installed; Gemini summarization disabled")

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

# Module-level sessions (initialized in main)
SESSION = None  # requests.Session for HTTP calls
GEMINI_CLIENT = None  # google.genai.Client for summarization (new SDK)


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
    # If no keywords configured, return None -> match everything
    if not keywords:
        return None
    escaped = [re.escape(k) for k in keywords]
    pattern = r"(?i)\b(" + "|".join(escaped) + r")\b"
    return re.compile(pattern)


def save_error_post(feed_url, error_message):
    """Save feed fetch error into _errors folder instead of _posts."""
    try:
        ERRORS_DIR.mkdir(parents=True, exist_ok=True)
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


def init_gemini_client(api_key, model="gemini-2.5-flash"):
    """
    Initialize Gemini API client for article summarization (Phase 1).
    Uses the new google-genai SDK (unified Google Gen AI SDK).
    
    Args:
        api_key: Gemini API key (from config or environment)
        model: Model name (default: gemini-2.5-flash, latest lightweight & fast)
    
    Returns:
        genai.Client object, or None if Gemini unavailable
    
    Raises:
        ValueError: If api_key is missing or invalid
    """
    global GEMINI_CLIENT
    
    if not GEMINI_AVAILABLE:
        logging.warning("Gemini not available (google-genai not installed)")
        return None
    
    if not api_key or not api_key.strip():
        logging.warning("GEMINI_API_KEY not provided; Gemini summarization disabled")
        return None
    
    try:
        GEMINI_CLIENT = genai.Client(api_key=api_key)
        logging.info("[GEMINI] Initialized client with model: %s", model)
        return GEMINI_CLIENT
    except Exception as e:
        logging.error("[GEMINI] Failed to initialize: %s", str(e))
        return None


def summarize_with_gemini(entry, keywords, prompt_template, config):
    """
    Summarize an article using Gemini API (Phase 1).
    Uses the new google-genai SDK (unified Google Gen AI SDK).
    
    Calls Gemini to generate a 2-3 sentence summary emphasizing keywords.
    If API fails, falls back to clean_summary() for graceful degradation.
    
    Args:
        entry: Feed entry dict with 'title', 'summary', 'description', 'content'
        keywords: List of keywords to emphasize
        prompt_template: Prompt template string with {keywords} and {article_text} placeholders
        config: Config dict with synthesis/error_handling settings
    
    Returns:
        dict: {
            'title': str (original or enhanced),
            'excerpt': str (2-3 sentences from Gemini or fallback),
            'keywords_hit': [str] (keywords found in article)
        }
    """
    if not GEMINI_CLIENT or not GEMINI_AVAILABLE:
        # Fallback: use existing clean_summary
        excerpt = clean_summary(entry.get("summary", "") or entry.get("description", ""))
        return {
            'title': entry.get('title', 'No Title'),
            'excerpt': excerpt,
            'keywords_hit': []
        }
    
    try:
        # Extract raw article text
        raw_summary = entry.get("summary", "") or entry.get("description", "")
        article_text = clean_summary(raw_summary)
        
        if not article_text or len(article_text.strip()) < 10:
            # Too short; skip Gemini, use fallback
            logging.debug("[GEMINI] Article text too short, using fallback")
            return {
                'title': entry.get('title', 'No Title'),
                'excerpt': article_text,
                'keywords_hit': []
            }
        
        # Build Gemini prompt
        keywords_str = ", ".join(keywords) if keywords else "none"
        prompt = prompt_template.format(
            keywords=keywords_str,
            article_text=article_text[:2000]  # Limit to 2000 chars for API cost
        )
        
        # Call Gemini API using new google-genai SDK
        response = GEMINI_CLIENT.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "max_output_tokens": 150,
                "temperature": 0.7,
            }
        )
        
        excerpt = response.text.strip() if response.text else ""
        
        # Validate response
        if not excerpt or len(excerpt) < 10:
            logging.debug("[GEMINI] Invalid response for '%s'; using fallback", entry.get('title'))
            excerpt = clean_summary(raw_summary)
        
        # Check which keywords were hit
        article_lower = article_text.lower()
        keywords_hit = [kw for kw in keywords if kw.lower() in article_lower]
        
        logging.debug("[GEMINI] Summarized '%s' (keywords hit: %s)", entry.get('title'), keywords_hit)
        
        return {
            'title': entry.get('title', 'No Title'),
            'excerpt': excerpt,
            'keywords_hit': keywords_hit
        }
    
    except Exception as e:
        logging.warning("[GEMINI] API error for '%s': %s; using fallback", entry.get('title'), str(e))
        # Graceful degradation: use raw summary
        excerpt = clean_summary(entry.get("summary", "") or entry.get("description", ""))
        return {
            'title': entry.get('title', 'No Title'),
            'excerpt': excerpt,
            'keywords_hit': []
        }


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
        if content_type and not any(x in content_type for x in ["xml", "rss", "atom", "xml+xml", "application/rss"]):
            logging.warning("Unexpected Content-Type for %s: %s — attempting to parse anyway", url, content_type)

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
    # If pattern is None => no keywords configured -> match everything
    if pattern is None:
        return True

    parts = [entry.get("title", ""), entry.get("summary", ""), entry.get("description", "")]
    # include common content blocks
    try:
        content = entry.get("content")
        if content:
            if isinstance(content, list):
                parts += [c.get("value", "") if isinstance(c, dict) else str(c) for c in content]
            else:
                parts.append(str(content))
    except Exception:
        pass

    text_to_check = " ".join([p for p in parts if p]).lower()
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
    """Format entries as markdown for a category, newest first.
    
    Phase 1: Uses Gemini-enhanced excerpts if available, falls back to clean_summary.
    """
    def get_pub_date(entry):
        if "published_parsed" in entry and entry.published_parsed:
            return datetime(*entry.published_parsed[:6], tzinfo=LOCAL_TZ)
        return datetime.now(LOCAL_TZ)

    sorted_entries = sorted(entries, key=get_pub_date, reverse=True)
    formatted = []
    for entry in sorted_entries:
        title = entry.get("title", "No Title")
        link = entry.get("link", "")
        
        # Phase 1: Use Gemini excerpt if available, else fall back to raw summary
        if entry.get('gemini_excerpt'):
            summary = entry.get('gemini_excerpt')
        else:
            raw_summary = entry.get("summary", "") or entry.get("description", "")
            summary = clean_summary(raw_summary)
        
        # Truncate if too long (2-3 sentences ~ 200 chars)
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
    POSTS_DIR.mkdir(parents=True, exist_ok=True)

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
        summary = clean_summary(entry.get("summary", "") or entry.get("description", ""))
        if len(summary) > 250:
            summary = summary[:247] + "..."
        
        safe_link = sanitize_url(entry.get("link", ""))
        highlights_section += f"{i}. **{title}** ({count} mentions)\n"
        highlights_section += f"   > {summary}\n"
        if safe_link:
            highlights_section += f"   > <a href=\"{safe_link}\">Read more</a>\n\n"
        else:
            highlights_section += f"   > Read more (link unavailable)\n\n"

    table = "| Category | Article Count |\n|---|---|\n"
    total_articles = 0
    for category, entries_text in sorted(content_by_category.items()):
        article_count = len([line for line in entries_text.split('\n') if line.strip().startswith('- **')])
        table += f"| {category} | {article_count} |\n"
        total_articles += article_count

    body = highlights_section
    body += "## Article Summary\n\n"
    body += table + f"\n**Total Articles Scanned: {total_articles}**\n\n"

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


def detect_trending_category(reports, highlights, trend_threshold=2):
    """
    Detect the trending category based on article frequency and highlights.
    
    Phase 2: Identifies which category has the most newsworthy content
    (most highlights or highest article count) for analyst opinion post.
    
    Args:
        reports: dict of {category: [entries]}
        highlights: list of (entry, count) tuples from deduplication
        trend_threshold: minimum mention count to consider a trend
    
    Returns:
        dict: {
            'category': str (trending category name),
            'article_count': int,
            'highlight_count': int,
            'top_articles': [entries] (top 3 from highlights in this category)
        }
    """
    if not reports:
        return None
    
    try:
        # Count articles per category
        category_counts = {cat: len(entries) for cat, entries in reports.items()}
        
        # Count highlights per category
        category_highlights = {}
        for entry, count in highlights:
            link = entry.get("link", "")
            cat_found = None
            for cat, entries in reports.items():
                if any(e.get("link") == link for e in entries):
                    cat_found = cat
                    break
            if cat_found:
                category_highlights[cat_found] = category_highlights.get(cat_found, 0) + count
        
        # Score: prioritize high highlight count, then article count
        scored_categories = []
        for cat in reports.keys():
            highlight_count = category_highlights.get(cat, 0)
            article_count = category_counts.get(cat, 0)
            # Score = highlights * 2 + articles (highlights weighted higher)
            score = (highlight_count * 2) + article_count
            scored_categories.append({
                'category': cat,
                'score': score,
                'article_count': article_count,
                'highlight_count': highlight_count
            })
        
        if not scored_categories:
            return None
        
        # Sort by score descending, pick top
        scored_categories.sort(key=lambda x: x['score'], reverse=True)
        trending = scored_categories[0]
        
        # Collect top articles from this category
        top_articles = [e for e, _ in highlights if any(
            e.get("link") == entry.get("link") 
            for entry in reports.get(trending['category'], [])
        )][:3]
        
        logging.info("[TRENDING] Category '%s' trending: %d highlights, %d articles", 
                    trending['category'], trending['highlight_count'], trending['article_count'])
        
        return {
            'category': trending['category'],
            'article_count': trending['article_count'],
            'highlight_count': trending['highlight_count'],
            'top_articles': top_articles
        }
    
    except Exception as e:
        logging.warning("[TRENDING] Error detecting trend: %s", str(e))
        return None


def create_weekly_scan_post(date_str, content_by_category, highlights):
    """
    Create the Weekly Scan post (aggregated news with trend metrics).
    
    Phase 2: Main news aggregation post showing all articles, highlights, and category stats.
    This is the refactored version of create_news_brief for Phase 2 output.
    
    Args:
        date_str: YYYY-MM-DD date string
        content_by_category: dict of {category: formatted_articles_str}
        highlights: list of (entry, count) tuples
    
    Returns:
        Path to created post file
    """
    POSTS_DIR.mkdir(parents=True, exist_ok=True)

    now_local = datetime.now(LOCAL_TZ)
    time_filename = now_local.strftime("%H-%M")
    filename = POSTS_DIR / f"{date_str}-{time_filename}-weekly-scan.md"

    date_object = datetime.strptime(date_str, "%Y-%m-%d")
    formatted_title_date = date_object.strftime("%b %d, %Y")
    time_front = now_local.strftime("%H:%M:%S %z")

    front_matter = f"""---
layout: post
title: "Weekly Scan: Cloud, Cybersecurity, AI News — {formatted_title_date}"
date: {date_str} {time_front}
categories: [newsbrief, weekly-scan]
---
"""

    # Highlights section
    highlights_section = "## Top Trending Stories\n\n"
    for i, (entry, count) in enumerate(highlights, start=1):
        title = entry.get("title", "No Title")
        summary = clean_summary(entry.get("summary", "") or entry.get("description", ""))
        if len(summary) > 250:
            summary = summary[:247] + "..."
        
        safe_link = sanitize_url(entry.get("link", ""))
        highlights_section += f"{i}. **{title}** ({count} mentions)\n"
        highlights_section += f"   > {summary}\n"
        if safe_link:
            highlights_section += f"   > <a href=\"{safe_link}\">Read more</a>\n\n"
        else:
            highlights_section += f"   > Read more (link unavailable)\n\n"

    # Summary table
    table = "| Category | Article Count |\n|---|---|\n"
    total_articles = 0
    for category, entries_text in sorted(content_by_category.items()):
        article_count = len([line for line in entries_text.split('\n') if line.strip().startswith('- **')])
        table += f"| {category} | {article_count} |\n"
        total_articles += article_count

    body = highlights_section
    body += "## Article Summary\n\n"
    body += table + f"\n**Total Articles Scanned: {total_articles}**\n\n"

    # Category sections
    for category in sorted(content_by_category.keys()):
        body += f"## {category}\n\n"
        body += content_by_category[category] + "\n\n"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(front_matter + body)
    
    logging.info("[WEEKLY SCAN] Created: %s", filename)
    return filename


def find_historical_context(keyword_topics, lookback_weeks=12):
    """
    Search past posts for similar topics to provide historical context.
    
    Args:
        keyword_topics: List of keywords/topics to search for (e.g., ['cybersecurity', 'ransomware'])
        lookback_weeks: How many weeks back to search
    
    Returns:
        list of dicts with {title, date, summary} from past posts
    """
    historical_posts = []
    cutoff_date = datetime.now(LOCAL_TZ) - timedelta(weeks=lookback_weeks)
    
    try:
        for post_file in sorted(POSTS_DIR.glob("*.md"), reverse=True):
            # Skip analyst opinion posts to avoid self-reference
            if "analyst-opinion" in post_file.name:
                continue
                
            file_mtime = datetime.fromtimestamp(post_file.stat().st_mtime, tz=LOCAL_TZ)
            if file_mtime < cutoff_date:
                break
            
            with open(post_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Check if any keywords appear in the post
            content_lower = content.lower()
            matching_keywords = [kw for kw in keyword_topics if kw.lower() in content_lower]
            
            if matching_keywords:
                # Extract title from front matter
                title_match = re.search(r'title:\s*["\']?([^"\'\n]+)["\']?', content)
                title = title_match.group(1) if title_match else post_file.stem
                
                # Extract date from front matter
                date_match = re.search(r'date:\s*(\d{4}-\d{2}-\d{2})', content)
                post_date = date_match.group(1) if date_match else "Unknown"
                
                # Extract first 200 chars of body (after front matter)
                body_start = content.find("---", content.find("---") + 3) + 3
                body = content[body_start:].strip()[:200]
                
                historical_posts.append({
                    'title': title,
                    'date': post_date,
                    'summary': body,
                    'keywords': matching_keywords
                })
    
    except Exception as e:
        logging.warning("[HISTORY] Failed to search historical context: %s", str(e))
    
    return historical_posts[:3]  # Return top 3 similar posts


def generate_gemini_opinion_analysis(article, category, historical_posts, config):
    """
    Generate deep Gemini analysis for analyst opinion post.
    
    Creates:
    - Expanded Executive Brief (~5 lines, 150-200 words)
    - Historical Context & Comparison
    - Risk/Opportunity Matrix
    
    Args:
        article: The article of the week
        category: Trend category
        historical_posts: List of similar past posts for comparison
        config: Config dict with synthesis settings
    
    Returns:
        dict with {executive_brief, historical_context, risk_assessment}
    """
    if not GEMINI_CLIENT or not GEMINI_AVAILABLE:
        return {
            'executive_brief': article.get('gemini_excerpt', clean_summary(article.get("summary", "") or article.get("description", ""))),
            'historical_context': "",
            'risk_assessment': ""
        }
    
    try:
        article_text = clean_summary(article.get("summary", "") or article.get("description", ""))[:1500]
        article_title = article.get("title", "Unknown")
        
        # Build historical context string
        history_context = ""
        if historical_posts:
            history_context = "\n\nRelated past articles:\n"
            for hp in historical_posts:
                history_context += f"- {hp['date']}: {hp['title']}\n"
        
        # Prompt 1: Expanded Executive Brief
        brief_prompt = f"""
Analyze this {category} article and provide an expanded executive brief (5 sentences, 150-200 words):

Title: {article_title}
Content: {article_text}

Write a professional, actionable executive summary that:
1. Explains WHAT happened and the immediate impact
2. Explains WHY it matters to organizations
3. Identifies the key risk or opportunity
4. Connects to broader industry trends
5. Hints at what organizations should monitor

Be specific, avoid generic language, and target cybersecurity professionals.
"""
        
        response_brief = GEMINI_CLIENT.models.generate_content(
            model="gemini-2.5-flash",
            contents=brief_prompt,
            config={"max_output_tokens": 250, "temperature": 0.7}
        )
        
        executive_brief = response_brief.text.strip() if response_brief.text else ""
        
        # Prompt 2: Historical Context & Novelty Assessment
        history_prompt = f"""
Article: {article_title}
{article_text}

{history_context if history_context else "No related historical articles found."}

Provide a HISTORICAL CONTEXT section (3-4 sentences):
1. Have we seen something similar before? If yes: when and how was it similar?
2. What has CHANGED or IMPROVED since then? OR if novel: what makes this unprecedented?
3. What should organizations have learned from past incidents? How does this incident differ?
4. Is this a recurring threat with new tactics, or something entirely new?

Be concise and insightful.
"""
        
        response_history = GEMINI_CLIENT.models.generate_content(
            model="gemini-2.5-flash",
            contents=history_prompt,
            config={"max_output_tokens": 200, "temperature": 0.7}
        )
        
        historical_context = response_history.text.strip() if response_history.text else ""
        
        # Prompt 3: Risk/Opportunity Matrix
        risk_prompt = f"""
Based on this article: {article_title}
{article_text}

Create a RISK/OPPORTUNITY ASSESSMENT with three timeframes:

**Immediate (0-30 days):** [What needs attention now?]
**Medium-term (30-90 days):** [What should we prepare for?]
**Strategic (90+ days):** [How does this reshape the landscape?]

For each, specify:
- Threat/Opportunity Type (e.g., Ransomware Evolution, New Compliance Requirement, AI Defense Gap)
- Impact Severity (High/Medium/Low)
- Recommended Action Priority

Keep it brief and actionable for a cybersecurity team.
"""
        
        response_risk = GEMINI_CLIENT.models.generate_content(
            model="gemini-2.5-flash",
            contents=risk_prompt,
            config={"max_output_tokens": 300, "temperature": 0.5}
        )
        
        risk_assessment = response_risk.text.strip() if response_risk.text else ""
        
        logging.info("[OPINION] Generated deep Gemini analysis for: %s", article_title)
        
        return {
            'executive_brief': executive_brief,
            'historical_context': historical_context,
            'risk_assessment': risk_assessment
        }
    
    except Exception as e:
        logging.warning("[OPINION] Gemini analysis failed: %s; using fallback", str(e))
        return {
            'executive_brief': article.get('gemini_excerpt', clean_summary(article.get("summary", "") or article.get("description", ""))),
            'historical_context': "",
            'risk_assessment': ""
        }


def create_analyst_opinion_post(date_str, trending_data, config):
    """
    Create the Analyst Opinion post (strategic commentary on article of the week).
    
    Phase 2 Enhanced: Single article deep-dive with:
    - Expanded Executive Brief (5 sentences)
    - Historical Context & Comparison
    - Risk/Opportunity Matrix (3 timeframes)
    
    Args:
        date_str: YYYY-MM-DD date string
        trending_data: dict from detect_trending_category() with category, articles, etc.
        config: config dict with synthesis settings
    
    Returns:
        Path to created post file
    """
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    
    if not trending_data:
        logging.warning("[OPINION] No trending data; skipping analyst opinion post")
        return None

    now_local = datetime.now(LOCAL_TZ)
    time_filename = now_local.strftime("%H-%M")
    filename = POSTS_DIR / f"{date_str}-{time_filename}-analyst-opinion.md"

    date_object = datetime.strptime(date_str, "%Y-%m-%d")
    formatted_title_date = date_object.strftime("%b %d, %Y")
    time_front = now_local.strftime("%H:%M:%S %z")

    category = trending_data['category']
    article_count = trending_data['article_count']
    highlight_count = trending_data['highlight_count']
    top_articles = trending_data.get('top_articles', [])

    if not top_articles:
        logging.warning("[OPINION] No articles in trending data; skipping opinion post")
        return None
    
    # Article of the week is the first (most trending)
    article_of_week = top_articles[0]

    front_matter = f"""---
layout: post
title: "Article of the Week: {category} — {formatted_title_date}"
date: {date_str} {time_front}
categories: [analysis, opinion, {category.lower().replace(' ', '-')}]
---
"""

    # Introduction
    intro_section = f"""## This Week's Trends: {category}

The **{category}** category captured significant attention this week with **{article_count}** articles and **{highlight_count}** trending stories.

Here's the **Article of the Week**—a deep dive into the most impactful story:

"""

    # Featured article
    article_title = article_of_week.get("title", "No Title")
    article_link = sanitize_url(article_of_week.get("link", ""))
    article_summary = article_of_week.get('gemini_excerpt', clean_summary(article_of_week.get("summary", "") or article_of_week.get("description", "")))
    
    featured_section = f"""## {article_title}

{article_summary}

"""
    if article_link:
        featured_section += f"<a href=\"{article_link}\">Read the full article</a>\n\n"

    # Get historical context and Gemini analysis
    keywords_for_history = [category.lower()] + (article_of_week.get('keywords_hit', []) if isinstance(article_of_week.get('keywords_hit'), list) else [])
    historical_posts = find_historical_context(keywords_for_history, lookback_weeks=12)
    
    gemini_analysis = generate_gemini_opinion_analysis(article_of_week, category, historical_posts, config)

    # Executive Brief section (expanded)
    executive_brief_section = f"""## Executive Brief

{gemini_analysis['executive_brief']}

"""

    # Historical Context section
    historical_section = ""
    if gemini_analysis['historical_context']:
        historical_section = f"""## How We Got Here: Historical Context

{gemini_analysis['historical_context']}

"""

    # Risk/Opportunity Assessment
    risk_section = ""
    if gemini_analysis['risk_assessment']:
        risk_section = f"""## Risk & Opportunity Matrix

{gemini_analysis['risk_assessment']}

"""

    # Closing
    closing_section = """---

**Analyst Note:** This article-of-the-week analysis synthesizes industry trends with expert assessment. For strategic decisions, conduct thorough validation with your security, compliance, and risk teams.
"""

    body = intro_section + featured_section + executive_brief_section + historical_section + risk_section + closing_section

    with open(filename, "w", encoding="utf-8") as f:
        f.write(front_matter + body)
    
    logging.info("[ANALYST OPINION] Created with deep analysis: %s", filename)
    return filename


def main():
    config = load_config()
    # allow overriding via env for quick debugging in CI/local
    log_level = os.environ.get("LOG_LEVEL", config.get("log_level", DEFAULTS["log_level"])).upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO), format="%(levelname)s: %(message)s")
    logging.info("Loaded config keys: %s", list(config.keys()))
    logging.info("Configured sources count: %d", len(config.get("sources", [])))
    logging.info("Configured keywords: %s", config.get("filters", {}).get("keywords", []))

    init_requests_session(
        retries=config.get("request_retries", DEFAULTS["request_retries"]),
        backoff=config.get("request_backoff", DEFAULTS["request_backoff"]),
        timeout=config.get("request_timeout", DEFAULTS["request_timeout"]),
        status_forcelist=config.get("request_status_forcelist", DEFAULTS["request_status_forcelist"]),
    )

    # Phase 1: Initialize Gemini API for summarization (if enabled and API key provided)
    gemini_config = config.get("gemini", {})
    gemini_api_key = os.environ.get("GEMINI_API_KEY", gemini_config.get("api_key", ""))
    gemini_enabled = config.get("synthesis", {}).get("enable_gemini_summarization", False)
    gemini_model = gemini_config.get("model", "gemini-1.5-flash")
    gemini_prompt_template = gemini_config.get("summarization_prompt", "")
    
    if gemini_enabled:
        init_gemini_client(gemini_api_key, gemini_model)
    else:
        logging.info("[GEMINI] Summarization disabled in config")

    logging.info("%s Starting news aggregation... %s", YELLOW, RESET)

    keywords = config.get("filters", {}).get("keywords", [])
    sources = config.get("sources", [])
    pattern = compile_keywords_pattern(keywords)

    logging.info("Configuration: sources=%d, keywords=%s, gemini_enabled=%s", len(sources), keywords, gemini_enabled)

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
                    
                    # Phase 1: Summarize with Gemini if enabled
                    if gemini_enabled and GEMINI_CLIENT and gemini_prompt_template:
                        summary_data = summarize_with_gemini(entry, keywords, gemini_prompt_template, config)
                        # Enhance entry with Gemini summary
                        entry['gemini_excerpt'] = summary_data['excerpt']
                        entry['gemini_title'] = summary_data['title']
                        entry['keywords_hit'] = summary_data['keywords_hit']
                    
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

    # Phase 2: Dual-post output (Weekly Scan + Analyst Opinion)
    phase2_enabled = config.get("synthesis", {}).get("enable_opinion_post", False)
    
    if phase2_enabled:
        # Create Weekly Scan post
        weekly_scan_file = create_weekly_scan_post(today, content_by_category, top_highlights)
        logging.info("%s [PHASE 2] Weekly Scan generated: %s", GREEN, weekly_scan_file)
        
        # Detect trending category for analyst opinion
        trend_threshold = config.get("synthesis", {}).get("trend_threshold", 2)
        trending_data = detect_trending_category(reports, top_highlights, trend_threshold=trend_threshold)
        
        # Create Analyst Opinion post
        if trending_data:
            opinion_file = create_analyst_opinion_post(today, trending_data, config)
            logging.info("%s [PHASE 2] Analyst Opinion generated: %s", GREEN, opinion_file)
        else:
            logging.warning("[PHASE 2] Could not detect trending category; skipping opinion post")
        
        logging.info("%s News aggregation complete: Weekly Scan + Analyst Opinion posts generated", GREEN)
    else:
        # Legacy Phase 1: Single post (news brief)
        create_news_brief(today, content_by_category, top_highlights)
        logging.info("%s [PHASE 1] News brief generated with %d articles across %d categories", GREEN, matched_entries, len(reports))


if __name__ == "__main__":
    main()