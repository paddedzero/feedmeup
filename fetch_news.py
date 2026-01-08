import feedparser
import yaml
import re
import requests
import logging
import os
import textwrap
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


def cluster_articles_by_theme(articles, num_clusters=3):
    """
    Cluster articles into thematic groups based on title and summary similarity.
    Uses fuzzy matching to group related stories together.
    
    Args:
        articles: list of (entry, count) tuples from highlights
        num_clusters: target number of clusters (default 3-5 groups)
    
    Returns:
        list of dicts: [{cluster_name, articles: [(entry, count), ...], article_count}, ...]
    """
    if not articles:
        return []
    
    try:
        from collections import Counter
        
        # Build clustering by grouping similar titles
        clusters = {}
        cluster_assignments = {}
        
        for idx, (entry, count) in enumerate(articles):
            if idx in cluster_assignments:
                continue
            
            title = (entry.get("title") or "").strip().lower()
            cluster_id = len(clusters)
            clusters[cluster_id] = {'articles': [(entry, count)], 'titles': [title]}
            cluster_assignments[idx] = cluster_id
            
            # Find similar articles for this cluster
            for other_idx in range(idx + 1, len(articles)):
                if other_idx in cluster_assignments:
                    continue
                
                other_entry, other_count = articles[other_idx]
                other_title = (other_entry.get("title") or "").strip().lower()
                similarity = rf_ratio(title.split(), other_title.split()) / 100.0
                
                if similarity >= 0.4:
                    clusters[cluster_id]['articles'].append((other_entry, other_count))
                    clusters[cluster_id]['titles'].append(other_title)
                    cluster_assignments[other_idx] = cluster_id
        
        # Generate cluster names from common keywords
        result = []
        for cluster_id, cluster_data in clusters.items():
            all_words = ' '.join(cluster_data['titles']).split()
            stop_words = {'the', 'a', 'an', 'and', 'or', 'is', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            keywords = [w for w in all_words if w not in stop_words and len(w) > 3]
            
            if keywords:
                top_keywords = Counter(keywords).most_common(2)
                cluster_name = ' & '.join([k[0].title() for k in top_keywords])
            else:
                cluster_name = f"Topic {cluster_id + 1}"
            
            result.append({
                'cluster_name': cluster_name,
                'articles': cluster_data['articles'],
                'article_count': len(cluster_data['articles'])
            })
        
        result.sort(key=lambda c: c['article_count'], reverse=True)
        return result[:num_clusters]
    
    except Exception as e:
        logging.warning("[CLUSTERING] Failed to cluster articles: %s", str(e))
        return []


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


def create_story_clusters_post(date_str, highlights):
    """Create a standalone narrative-style blog post from story clusters."""
    from datetime import datetime
    
    POSTS_DIR.mkdir(parents=True, exist_ok=True)

    now_local = datetime.now(LOCAL_TZ)
    time_filename = now_local.strftime("%H-%M")
    filename = POSTS_DIR / f"{date_str}-{time_filename}-weekly-brief.md"

    date_object = datetime.strptime(date_str, "%Y-%m-%d")
    formatted_title_date = date_object.strftime("%b %d, %Y")
    time_front = now_local.strftime("%H:%M:%S %z")

    front_matter = f"""---
layout: post
title: "This Week in Security: A Briefing — {formatted_title_date}"
date: {date_str} {time_front}
categories: [newsbrief, weekly-brief]
---
"""

    # Generate clusters
    clusters = cluster_articles_by_theme(highlights, num_clusters=5) if highlights else []
    
    intro = f"""## This Week in Security: What's Trending

Here's your briefing on the week's most important security stories, organized by theme. We've identified **{len(clusters)}** key topics capturing industry attention from across **{sum(c['article_count'] for c in clusters)}** trending stories.

"""
    
    body = intro
    
    # Generate narrative sections for each cluster
    for idx, cluster in enumerate(clusters, start=1):
        cluster_name = cluster['cluster_name']
        articles = cluster['articles']
        
        # Cluster header
        body += f"### {idx}. {cluster_name} ({len(articles)} stories)\n\n"
        
        # Narrative paragraph with top articles
        body += f"The **{cluster_name}** theme captured {len(articles)} trending stories this week. "
        
        if len(articles) >= 2:
            top_articles = articles[:2]
            body += f"Key developments include:\n\n"
            for rank, (entry, count) in enumerate(top_articles, start=1):
                title = entry.get("title", "No Title")
                summary = clean_summary(entry.get("summary", "") or entry.get("description", ""))
                if len(summary) > 200:
                    summary = summary[:197] + "..."
                safe_link = sanitize_url(entry.get("link", ""))
                
                body += f"**{rank}. {title}** ({count} mentions)\n"
                body += f"   {summary}\n"
                if safe_link:
                    body += f"   [Read more]({safe_link})\n\n"
                else:
                    body += f"\n"
        
        if len(articles) > 2:
            remaining = articles[2:]
            body += f"\nOther notable stories: "
            titles = [e.get("title", "Untitled") for e, c in remaining[:3]]
            body += ", ".join(titles)
            body += "\n"
        
        body += f"\n---\n\n"
    
    closing = """## Stay Informed

These thematic groupings highlight how similar security issues are emerging across multiple vendors and technologies this week. For each topic, consider how your organization's security strategy aligns with the trends.
"""
    
    body += closing
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(front_matter + body)
    
    return str(filename)


def create_narrative_briefing(highlights):
    """
    Create an 800-1000 word narrative news briefing from top stories.
    Conversational, friendly tone with critical stories first, includes punchy quotes,
    and forward-looking recommendations ("monitor these", "have a look at these").
    
    Args:
        highlights: list of (entry, count) tuples (top 10 stories)
    
    Returns:
        Narrative briefing text
    """
    if not highlights:
        return ""
    
    # Separate stories by criticality
    critical_stories = []  # Threats, CVEs, breaches
    trend_stories = []     # Emerging trends, new techniques
    tool_stories = []      # Tools, updates, releases
    
    for entry, count in highlights[:10]:
        title = entry.get("title", "").lower()
        category = entry.get('_article_category', '').lower()
        summary = (entry.get("summary", "") or entry.get("description", "")).lower()
        content_sample = (title + " " + category + " " + summary[:200]).lower()
        
        is_critical = any(keyword in content_sample for keyword in 
                         ['breach', 'cve-', 'vulnerability', 'threat', 'ransomware', 
                          'malware', 'attack', 'exploit', 'zero-day', 'critical'])
        is_trend = any(keyword in content_sample for keyword in 
                      ['trend', 'emerging', 'analysis', 'technique', 'pattern', 'report'])
        
        if is_critical:
            critical_stories.append((entry, count))
        elif is_trend:
            trend_stories.append((entry, count))
        else:
            tool_stories.append((entry, count))
    
    # Build narrative
    briefing = "## This Week in Security: Your News Briefing\n\n"
    
    # Extract 3-5 most critical headlines
    top_stories = []
    for entry, count in highlights[:5]:
        title = entry.get("title", "")
        if title:
            # Shorten long titles for readability
            if len(title) > 70:
                title = title[:67].rsplit(' ', 1)[0] + "..."
            top_stories.append((title, count))
            
    # Combine Intro + Rundown into a single paragraph
    total_stories = len(highlights[:10])
    paragraph = f"Welcome to your weekly security roundup. We've tracked down the **{total_stories} most important stories** this week—the ones everyone's talking about, from critical threats to emerging trends that could shape your security posture. "
    
    if top_stories:
        t1, c1 = top_stories[0]
        paragraph += f"Leading the news this week is **{t1}**, which has sparked conversation across {c1} sources. "
        
        if len(top_stories) > 1:
            t2, c2 = top_stories[1]
            paragraph += f"Meanwhile, the industry is closely tracking **{t2}** with {c2} mentions, "
            
            remaining = top_stories[2:]
            if remaining:
                titles = [f"**{t}**" for t, c in remaining]
                if len(titles) == 1:
                    paragraph += f"along with emerging details on {titles[0]}. "
                else:
                    last = titles.pop()
                    joined = ", ".join(titles)
                    paragraph += f"along with emerging details on {joined}, and {last}. "
            else:
                paragraph = paragraph.rstrip(", ") + ". "
        
        paragraph += "Here's the full breakdown of what you need to know."
    else:
        paragraph += "Let's dive in."
        
    # Wrap text to prevention horizontal scrolling / code block rendering issues
    briefing += textwrap.fill(paragraph, width=100) + "\n\n"
    
    # Critical stories section (if any)
    if critical_stories:
        briefing += "### 🚨 Critical Threats This Week\n\n"
        briefing += "First, the stories that demand your immediate attention:\n\n"
        
        for idx, (entry, count) in enumerate(critical_stories[:3], 1):
            title = entry.get("title", "No Title")
            summary = clean_summary(entry.get("summary", "") or entry.get("description", ""))
            link = sanitize_url(entry.get("link", ""))
            
            # Extract punchy quote or create one from summary
            sentences = [s.strip() for s in summary.split('.') if len(s.strip()) > 20]
            quote = sentences[0][:120] if sentences else summary[:120]
            
            briefing += f"**{idx}. {title}**\n"
            briefing += f"   Mentioned across {count} industry sources this week. {quote.rstrip('.')}.\n"
            if link:
                briefing += f"   [Get the details →]({link})\n\n"
            else:
                briefing += f"\n"
    
    # Trend stories section
    if trend_stories:
        briefing += "### 📈 Emerging Trends & Analysis\n\n"
        briefing += "Here's what the security community is exploring and learning:\n\n"
        
        for idx, (entry, count) in enumerate(trend_stories[:3], 1):
            title = entry.get("title", "No Title")
            summary = clean_summary(entry.get("summary", "") or entry.get("description", ""))
            link = sanitize_url(entry.get("link", ""))
            
            sentences = [s.strip() for s in summary.split('.') if len(s.strip()) > 20]
            quote = sentences[0][:120] if sentences else summary[:120]
            
            briefing += f"**{idx}. {title}**\n"
            briefing += f"   {quote.rstrip('.')}. Catching attention from {count} news sources.\n"
            if link:
                briefing += f"   [Learn more →]({link})\n\n"
            else:
                briefing += f"\n"
    
    # Tools & updates section
    if tool_stories:
        briefing += "### 🛠️ Tools, Updates & Releases\n\n"
        briefing += "New capabilities and releases worth knowing about:\n\n"
        
        for idx, (entry, count) in enumerate(tool_stories[:3], 1):
            title = entry.get("title", "No Title")
            summary = clean_summary(entry.get("summary", "") or entry.get("description", ""))
            link = sanitize_url(entry.get("link", ""))
            
            sentences = [s.strip() for s in summary.split('.') if len(s.strip()) > 20]
            quote = sentences[0][:100] if sentences else summary[:100]
            
            briefing += f"**{idx}. {title}**\n"
            briefing += f"   {quote.rstrip('.')}. Referenced in {count} stories this week.\n"
            if link:
                briefing += f"   [Explore →]({link})\n\n"
            else:
                briefing += f"\n"
    
    # Closing with forward-looking recommendations
    briefing += "### What You Should Do Next\n\n"
    briefing += "**Monitor these** in your environment next week:\n"
    briefing += "- Any new CVE announcements related to systems you operate\n"
    briefing += "- Emerging attack techniques being discussed in the community\n"
    briefing += "- Updates and patches for tools your team uses\n\n"
    briefing += "**Have a look at** the full deep-dives in the trending stories below. Each one provides context that could inform your security decisions this week.\n\n"
    
    briefing += "---\n\n"
    return briefing


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

    # Highlights section with narrative briefing + consolidated threat intel/vulnerability
    highlights_section = ""
    
    # Add narrative news briefing at the top
    if highlights:
        narrative = create_narrative_briefing(highlights)
        if narrative:
            highlights_section += narrative
    
    # Top Trending Stories - detailed list
    highlights_section += "## Top Trending Stories\n\n"
    
    # Separate threat intel/vulnerability from other articles
    threat_intel_vuln = []
    other_highlights = []
    
    for entry, count in highlights:
        category = entry.get('_article_category', '')
        # Check for threat intel or vulnerability categories (handle various formats)
        if 'threat' in category.lower() or 'vulnerability' in category.lower() or 'cve' in category.lower():
            threat_intel_vuln.append((entry, count))
        else:
            other_highlights.append((entry, count))
    
    # Build top trending with consolidated threat intel/vulnerability entry
    item_num = 1
    
    # First add consolidated threat intel & vulnerability if they exist
    if threat_intel_vuln:
        top_threats = sorted(threat_intel_vuln, key=lambda x: x[1], reverse=True)[:3]
        
        highlights_section += f"{item_num}. **Key Threat Intel & Vulnerability Stories** ({sum(c for e, c in threat_intel_vuln)} mentions)\n"
        highlights_section += "   > This week's critical security updates and vulnerability disclosures:\n"
        for entry, count in top_threats:
            title = entry.get("title", "No Title")
            highlights_section += f"   > • {title} ({count} mentions)\n"
        highlights_section += "\n"
        item_num += 1
    
    # Then add other trending stories
    for entry, count in other_highlights:
        title = entry.get("title", "No Title")
        summary = clean_summary(entry.get("summary", "") or entry.get("description", ""))
        if len(summary) > 250:
            summary = summary[:247] + "..."
        
        safe_link = sanitize_url(entry.get("link", ""))
        highlights_section += f"{item_num}. **{title}** ({count} mentions)\n"
        highlights_section += f"   > {summary}\n"
        if safe_link:
            highlights_section += f"   > <a href=\"{safe_link}\">Read more</a>\n\n"
        else:
            highlights_section += f"   > Read more (link unavailable)\n\n"
        item_num += 1

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
    logging.info("[PHASE 2] Weekly Scan (with Narrative News Briefing) + Analyst Opinion posts generated successfully")
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
    Generate investigative journalism analysis for analyst opinion post.
    
    Uses gemini-3-flash-preview for cost-effective reasoning depth.
    Hybrid Strategy: Flash for investigative analysis, Flash for weekly summaries.
    
    Transforms article into deep investigative journalism with technical accountability:
    - Technical Analysis & Threat Intelligence (900-1100 words): Technical breakdown, defense failures, threat ecosystem, attribution, monetization
    - Defense Strategy (600+ words): Immediate actions, medium-term planning, strategic vision
    
    Args:
        article: The article of the week
        category: Trend category
        historical_posts: List of similar past posts for comparison
        config: Config dict with synthesis settings
    
    Returns:
        dict with {technical_analysis, defense_strategy}
    """
    if not GEMINI_CLIENT or not GEMINI_AVAILABLE:
        return {
            'technical_analysis': article.get('gemini_excerpt', clean_summary(article.get("summary", "") or article.get("description", ""))),
            'defense_strategy': ""
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
        
        # Prompt 1: Combined Technical Analysis & Threat Intelligence (Investigative Journalism)
        # Merges technical deep-dive with threat ecosystem for cohesive 900-1100 word narrative
        technical_prompt = f"""
You are a senior cybersecurity analyst writing an investigative article about this {category} story.

Title: {article_title}
Content: {article_text}

{history_context if history_context else ""}

Write a comprehensive TECHNICAL ANALYSIS & THREAT INTELLIGENCE section (6-7 paragraphs, 900-1100 words) that tells a cohesive story:

**Section Opening (Paragraph 1): What Happened & Technical Breakdown**
- Explain the incident/vulnerability/trend in technical detail
- If it's an attack: describe the attack chain (initial access → persistence → lateral movement → impact)
- If it's a vulnerability: explain the flaw, affected systems, exploitation mechanics
- Include specific technical details: CVE IDs, product versions, protocols, techniques used

**Technical Deep-Dive (Paragraphs 2-3): Why This Succeeds & Defense Failures**
- Explain WHY this attack/vulnerability is effective against defenses
- What specific security controls fail or are bypassed? (EDR, SIEM, WAF, etc.)
- Why do defenders miss this? (detection blind spots, configuration errors, vendor gaps)
- Provide concrete examples: "EDR solutions miss this because they don't monitor X behavior"
- Historical context: "Have we seen similar techniques before? How have attackers evolved this?"
- Compare to past incidents: "This mirrors the 2023 [incident] but adds [new capability]"

**Threat Ecosystem (Paragraphs 4-5): Who Exploits This & Monetization**
- Who benefits from this? (specific threat actors, APT groups, criminal forums)
- Attribution clues: infrastructure patterns, TTPs, targeting preferences
- Name specific actors/groups if applicable (e.g., "Scattered Spider", "Kimsuky", "LockBit")
- How do attackers monetize this? (ransomware payments, data sales, crypto mixers, fraud)
- Criminal marketplace dynamics: who sells what, pricing, access models
- Supply chain: initial access brokers → ransomware operators → money launderers

**Ecosystem Evolution & Outlook (Paragraphs 6-7): Timeline & Predictions**
- How has this threat evolved over time? (timeline: first seen [date], widespread by [date])
- Escalation patterns: increasing sophistication, new targets, cross-border coordination
- Real-world impact: Who is affected? (sectors, organization types, cascade effects)
- Future trajectory: "Expect to see [trend] accelerate in [timeframe] because [reason]"
- Why this matters for cybersecurity professionals AND business decision-makers

Tone: Investigative journalism with technical accountability. Deep technical expertise + real-world impact analysis. Be specific with product names, CVE IDs, threat actor TTPs, monetization details, and vendor accountability. Avoid generic security advice—focus on HOW and WHY attacks succeed against current defenses, not just THAT they succeed. Examine defense failures and gaps with nuance.
"""
        
        response_technical = GEMINI_CLIENT.models.generate_content(
            model="gemini-3-flash",
            contents=technical_prompt,
            config={"max_output_tokens": 1200, "temperature": 0.4}
        )
        
        # Handle response - might be in different format
        if hasattr(response_technical, 'text'):
            technical_analysis = response_technical.text.strip()
        elif hasattr(response_technical, 'content'):
            technical_analysis = response_technical.content.strip()
        else:
            technical_analysis = str(response_technical).strip()
        
        logging.debug("[OPINION] Technical analysis response type: %s, length: %d", type(response_technical), len(technical_analysis) if technical_analysis else 0)
        
        # Prompt 2: Defense Strategy & Actionable Intelligence (Detection, Mitigation, Strategic Actions)
        defense_prompt = f"""
Provide DEFENSE STRATEGY & ACTIONABLE INTELLIGENCE for security teams.

Article: {article_title}
{article_text}

Create a comprehensive defense guide with three timeframes:

**IMMEDIATE ACTIONS (0-30 days) - Tactical Response**
Provide 3-5 SPECIFIC, TECHNICAL actions:
- Concrete detection rules: "Deploy SIEM query for [specific behavior/IOC]"
- Patch urgency: "Patch CVE-XXXX in [affected systems] - exploited in wild"
- Configuration hardening: "Enable [specific setting] in [security tool]"
- Hunting queries: "Search logs for [specific indicator/pattern]"
- Isolation/containment: "Segment [critical assets] from [network zone]"

Be SPECIFIC: name CVEs, products, log sources, actual query syntax if possible.

**MEDIUM-TERM PLANNING (30-90 days) - Process & Architecture**
Provide 3-4 strategic improvements:
- Architecture changes: "Implement network segmentation for [critical assets]"
- Process improvements: "Conduct tabletop exercise simulating [attack scenario]"
- Vendor assessment: "Review [vendor] SLAs for [incident response capability]"
- Capability gaps: "Invest in [technology/tool] to address [detection gap]"
- Training: "Train SOC analysts on [specific technique/tool]"

**LONG-TERM VISION (90+ days) - Strategic Transformation**
Provide 2-3 strategic shifts:
- Philosophy: "Shift from perimeter defense to assume-breach model"
- Investment: "Prioritize [technology category] over [legacy approach] because [reason]"
- Collaboration: "Join [industry group] for [threat intelligence sharing]"
- Resilience: "Build [capability] to recover from [specific scenario]"

For each timeframe, explain WHY (tied to the technical analysis). Avoid generic advice.
"""
        
        response_defense = GEMINI_CLIENT.models.generate_content(
            model="gemini-3-flash",
            contents=defense_prompt,
            config={"max_output_tokens": 800, "temperature": 0.3}
        )
        
        # Handle response - might be in different format
        if hasattr(response_defense, 'text'):
            defense_strategy = response_defense.text.strip()
        elif hasattr(response_defense, 'content'):
            defense_strategy = response_defense.content.strip()
        else:
            defense_strategy = str(response_defense).strip()
        
        logging.debug("[OPINION] Defense strategy response type: %s, length: %d", type(response_defense), len(defense_strategy) if defense_strategy else 0)
        
        logging.info("[OPINION] Generated investigative journalism analysis for: %s", article_title)
        
        return {
            'technical_analysis': technical_analysis,
            'defense_strategy': defense_strategy
        }
    
    except Exception as e:
        logging.warning("[OPINION] Gemini analysis failed: %s; using fallback", str(e))
        
        # Provide structured fallback content when Gemini is unavailable
        article_summary = article.get('gemini_excerpt', clean_summary(article.get("summary", "") or article.get("description", "")))
        
        # Create a basic technical analysis from the article summary and category
        fallback_technical = f"""
**Technical Overview**

{article_summary}

**Key Points**

This article relates to the {category.upper()} security category. The content addresses important developments in this area that security teams should be aware of.

*Note: Full technical analysis requires Gemini API access for deep investigative journalism synthesis.*
"""
        
        # Create structured fallback defense strategy with action items
        fallback_defense = f"""
**Immediate Actions (0-30 days)**

1. Review this article for relevant context to your organization's security posture
2. Share findings with your security team for discussion
3. Assess applicability to your systems and infrastructure

**Medium-Term Planning (30-90 days)**

1. Incorporate findings into your security strategy review
2. Update relevant security policies if needed
3. Schedule team training if new threats are identified

**Long-Term Vision (90+ days)**

1. Track evolution of this threat/trend over time
2. Integrate learnings into future security architecture decisions
3. Build defense capabilities to address identified gaps

*Full defense strategy recommendations require Gemini API access for comprehensive threat analysis.*
"""
        
        return {
            'technical_analysis': fallback_technical,
            'defense_strategy': fallback_defense
        }


def create_analyst_opinion_post(date_str, trending_data, config):
    """
    Create the Analyst Opinion post with Top 3 Articles of the Week.
    
    Phase 3 Enhanced: Deep investigative analysis for top 3 trending stories:
    - Full technical analysis for each article (900-1100 words per story)
    - Defense strategy for each article (600+ words per story)
    - Maintains complete analytical depth across all 3 articles
    
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
    
    # Get top 3 articles (or fewer if not available)
    top_3_articles = top_articles[:3]

    front_matter = f"""---
layout: post
title: "Analyst Top 3: {category} — {formatted_title_date}"
date: {date_str} {time_front}
categories: [analysis, opinion, {category.lower().replace(' ', '-')}]
---
"""

    # Introduction
    intro_section = f"""## This Week's Top 3: {category}

The **{category}** category captured significant attention this week with **{article_count}** articles and **{highlight_count}** trending stories.

Here are the **Top 3 Articles of the Week**—comprehensive analysis of the most impactful stories:

"""

    # Build full analysis for each of the top 3 articles
    articles_body = ""
    for rank, article in enumerate(top_3_articles, start=1):
        article_title = article.get("title", "No Title")
        article_link = sanitize_url(article.get("link", ""))
        article_summary = article.get('gemini_excerpt', clean_summary(article.get("summary", "") or article.get("description", "")))
        
        # Article header
        articles_body += f"## Article {rank}: {article_title}\n\n"
        articles_body += f"{article_summary}\n\n"
        if article_link:
            articles_body += f"<a href=\"{article_link}\">Read the full article</a>\n\n"
        
        # Get historical context and Gemini analysis for this article
        keywords_for_history = [category.lower()] + (article.get('keywords_hit', []) if isinstance(article.get('keywords_hit'), list) else [])
        historical_posts = find_historical_context(keywords_for_history, lookback_weeks=12)
        gemini_analysis = generate_gemini_opinion_analysis(article, category, historical_posts, config)
        
        # Technical Analysis section with full depth
        articles_body += f"### Technical Analysis: What's Really Happening\n\n"
        articles_body += f"{gemini_analysis['technical_analysis']}\n\n"
        
        # Defense Strategy section with full depth
        if gemini_analysis['defense_strategy']:
            articles_body += f"### Defense Strategy: What Security Teams Should Do\n\n"
            articles_body += f"{gemini_analysis['defense_strategy']}\n\n"
        
        articles_body += "---\n\n"
    
    # Closing
    closing_section = """**Analyst Note:** These top 3 articles this week synthesize industry trends with expert assessment. For strategic decisions, conduct thorough validation with your security, compliance, and risk teams."""

    body = intro_section + articles_body + closing_section

    with open(filename, "w", encoding="utf-8") as f:
        f.write(front_matter + body)
    
    logging.info("[ANALYST OPINION] Created with Top 3 deep analysis: %s", filename)
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
                    # Store category in entry for later filtering
                    entry['_article_category'] = category
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

    # Phase 2: Dual-post output (Weekly Scan + Analyst Opinion + Story Clusters)
    phase2_enabled = config.get("synthesis", {}).get("enable_opinion_post", False)
    
    if phase2_enabled:
        # Create Weekly Scan post (with Story Clusters briefing + consolidated threat intel/vulnerability)
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
        
        logging.info("%s News aggregation complete: Weekly Scan (with Story Clusters) + Analyst Opinion posts generated", GREEN)
    else:
        # Legacy Phase 1: Single post (news brief)
        create_news_brief(today, content_by_category, top_highlights)
        logging.info("%s [PHASE 1] News brief generated with %d articles across %d categories", GREEN, matched_entries, len(reports))


if __name__ == "__main__":
    main()