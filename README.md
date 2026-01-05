# feedmeup — Automated Tech News Aggregator

![GitHub Actions](https://img.shields.io/github/actions/workflow/status/paddedzero/feedmeup/news.yml?branch=main)
![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live-success)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Jekyll](https://img.shields.io/badge/Jekyll-Chirpy%20Theme-red)

**Live Site**: [https://paddedzero.github.io/feedmeup](https://paddedzero.github.io/feedmeup)

An intelligent news aggregator that automatically curates, summarizes, and publishes technology news from 40+ sources covering AI/LLM, Cloud Security, Cybersecurity, Vulnerabilities, Threat Intelligence, and Asia-Pacific regulatory updates.

---

## 🎯 What This Project Does

**feedmeup** is a fully automated news pipeline that:

1. **Fetches** news from 40+ RSS/Atom feeds across multiple categories
2. **Filters** content using configurable keyword matching
3. **Deduplicates** similar articles using fuzzy string matching
4. **Summarizes** content using Google Gemini AI (1.5 Flash model)
5. **Generates** two types of posts:
   - **Weekly Scan**: Comprehensive news roundup with categorized articles
   - **Analyst Opinion**: AI-powered analysis with trends and strategic insights
6. **Publishes** automatically to GitHub Pages with the professional Chirpy Jekyll theme
7. **Runs weekly** via GitHub Actions (Mondays 8 AM UTC) or on-demand

---

## 🏗️ Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub Actions Workflow (Scheduled: Mon 8AM UTC)          │
├─────────────────────────────────────────────────────────────┤
│  1. fetch_news.py → Aggregates 40+ RSS feeds              │
│  2. Filters by keywords (config.yaml)                      │
│  3. Deduplicates using RapidFuzz                          │
│  4. Gemini AI → Generates summaries & analysis            │
│  5. Creates Jekyll markdown posts                          │
│  6. Publishes to GitHub Pages                             │
│  7. GitHub Pages → Renders with Chirpy theme              │
└─────────────────────────────────────────────────────────────┘
```

---

## � Backup & Recovery Strategy

**gh-pages-feedmeup-snapshot branch**: Automated weekly snapshot backup of the main branch  
**Schedule**: Every Sunday at 2 AM UTC  
**Purpose**: Emergency recovery point in case main branch becomes unstable

If main branch breaks and needs recovery:
1. Check gh-pages-feedmeup-snapshot for the last known-good state
2. Create a recovery branch from gh-pages-feedmeup-snapshot: `git checkout -b recovery gh-pages-feedmeup-snapshot`
3. Review changes and test
4. If confirmed safe, force update main: `git push origin recovery:main -f`

This automated backup system ensures you always have a fallback point without manual effort.

---

## �📰 News Sources (40+ Feeds)

### LLM & AI (3 sources)
- OpenAI News, Google AI Blog, Microsoft AI Blog

### Cloud (3 sources)
- AWS News, Azure Updates, Google Cloud Blog

### Cybersecurity (10 sources)
- Dark Reading, Krebs on Security, The Hacker News, BleepingComputer, SC Magazine, SecurityWeek, Help Net Security, Bruce Schneier Blog, TechRadar Pro Security, The Register

### Vulnerability & CVE (7 sources)
- CVE Feed, CVE Details, Rapid7, Tenable Research, VulnDB, ExploitDB, Qualys VMDR

### Threat Intelligence (7 sources)
- Recorded Future, CrowdStrike, Cisco Talos, Malwarebytes Labs, Palo Alto Unit 42, SANS ISC, Microsoft Security Blog

### Asia-Pacific Regulation (8 sources)
- Singapore MAS, Singapore CSA, Japan NISC, India CERT-In, Hong Kong PCPD, Philippines NPC, Korea KISA, Malaysia MyCERT

---

## 🚀 How It Works

### 1. News Aggregation (`fetch_news.py`)

```python
# Parallel feed fetching with retry logic
- HTTP requests with 3 retries, exponential backoff
- 15-second timeout per feed
- 30-day lookback window
- HTML-to-plaintext conversion with BeautifulSoup
```

### 2. Keyword Filtering

```yaml
# config.yaml
filters:
  keywords:
    - vulnerability
    - zero-day
    - ransomware
    - data breach
    # ... configurable list
```

- Word-boundary regex matching (case-insensitive)
- Searches across title + summary + content
- Empty list = matches everything

### 3. Deduplication

- Fuzzy title matching using RapidFuzz (threshold 0.8)
- Groups similar stories across feeds
- Enforces max 2 articles per domain
- Highlights top 10 stories by frequency × recency

### 4. AI Summarization (Gemini)

**Weekly Scan Post**:
- Categorized article lists with summaries
- Highlights section with top stories
- Publication count per category

**Analyst Opinion Post**:
- Executive summary
- Key trends and patterns
- Strategic implications
- Regional analysis for APAC content
- Actionable recommendations

### 5. Jekyll Post Generation

```markdown
---
layout: post
title: "Weekly Tech News Scan - January 4, 2026"
date: 2026-01-04 08:00:00 -0500
categories: [newsbrief]
tags: [weekly-scan, automation]
---
```

- Timestamped filenames prevent collisions
- HTML anchors for feed links (preserves HTML)
- Front matter with timezone support

### 6. Automated Deployment

**GitHub Actions Workflow**:
```yaml
- Runs: Monday 08:00 UTC (schedule) or manual dispatch
- Installs: Python + Ruby dependencies
- Executes: fetch_news.py
- Publishes: Generated posts to GitHub Pages
```

---

## ⚙️ Configuration

### Adding/Removing Feeds

Edit [`config.yaml`](config.yaml):

```yaml
sources:
  - name: Your News Source
    url: https://example.com/feed.xml
    category: Security  # Existing: LLM, Cloud, Security, Vulnerability, ThreatIntel, Regulation
```

**Categories**: Assign existing category or create new one (becomes section header in posts)

### Adjusting Keyword Filters

```yaml
filters:
  keywords:
    - your-keyword
    - another-term
    # Literal strings, matched at word boundaries
```

### Performance Tuning

```yaml
fuzz_threshold: 0.8          # Deduplication sensitivity (0.0-1.0)
max_per_domain: 2            # Max articles per domain in highlights
max_results: 10              # Top N highlighted stories
request_retries: 3           # HTTP retry attempts
```

### Gemini AI Configuration

Set environment variable in GitHub Actions secrets:
```bash
GEMINI_API_KEY=your-google-api-key
```

---

## 🛠️ Local Development

### Setup

```powershell
# Clone repository
git clone https://github.com/paddedzero/feedmeup.git
cd feedmeup

# Create Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Set Gemini API key (optional, for AI features)
$env:GEMINI_API_KEY="your-api-key"
```

### Run Aggregation Script

```powershell
python fetch_news.py
```

Check `_posts/` folder for generated markdown files.

### Test Locally with Jekyll

```powershell
# Install Ruby dependencies
bundle install

# Run Jekyll server
bundle exec jekyll serve

# Visit http://localhost:4000
```

### Run Tests

```powershell
pytest tests/
```

---

## 📁 Project Structure

```
feedmeup/
├── fetch_news.py              # Main aggregation script
├── config.yaml                # Feed sources & filters
├── requirements.txt           # Python dependencies
├── Gemfile                    # Ruby/Jekyll dependencies
├── _config.yml                # Jekyll site configuration
├── .github/
│   ├── workflows/
│   │   └── news.yml          # GitHub Actions automation
│   ├── copilot-instructions.md
│   └── LESSONS_LEARNED.md    # Development history & patterns
├── _posts/                    # Generated Jekyll posts
├── _tabs/                     # Site navigation tabs
├── _data/                     # Jekyll data files
├── _plugins/                  # Jekyll plugins
├── tests/                     # Test suite
└── _backup/                   # Historical diagnostic files
```

---

## 🤝 Contributing

This is a personal automation project, but suggestions welcome:

1. **Feed Suggestions**: Open an issue with feed URL + category
2. **Bug Reports**: Include workflow logs and error details
3. **Feature Ideas**: Describe use case and expected behavior

---

## 📄 License

This project is open source for educational purposes. Respect RSS feed terms of service and rate limits when adapting this code.

---

## 🙏 Acknowledgments

- **Chirpy Theme**: [cotes2020/jekyll-theme-chirpy](https://github.com/cotes2020/jekyll-theme-chirpy)
- **Google Gemini**: AI summarization powered by Gemini 1.5 Flash
- **GitHub Actions**: Free automation platform
- **Feed Sources**: 40+ news organizations providing RSS feeds

---

## 📬 Contact

- **Live Site**: [https://paddedzero.github.io/feedmeup](https://paddedzero.github.io/feedmeup)
- **Repository**: [https://github.com/paddedzero/feedmeup](https://github.com/paddedzero/feedmeup)
- **Issues**: Use GitHub Issues for bug reports

---

**Last Updated**: January 4, 2026  
