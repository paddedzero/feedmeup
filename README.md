Here’s a short but clear README draft you can drop into your repo to remind yourself how the whole setup works and what to edit.

---

## **README.md**

### 📌 Project Overview

This project **automatically collects and publishes** curated news on AI, cybersecurity, cloud security, regulatory changes, and Asia-Pacific cyber policy.
It uses a **Python script** to pull news from selected sources, filter them using keywords, format them as Jekyll posts, and publish them to a **static site on GitHub Pages**.

---

### ⚙ How It Works

1. **`fetch_news.py`** — Fetches headlines, applies keyword filters, and generates Markdown files in the Jekyll `_posts` folder.
2. **`config.yaml`** — Holds your **keyword filters** and **news source list**. Edit this file to change what content is pulled.
3. **GitHub Actions (`.github/workflows/news.yml`)** — Runs the script on schedule, commits new posts, and pushes them to GitHub Pages.
4. **Jekyll site** — Renders the `_posts` Markdown files as blog posts at your GitHub Pages URL.

---

# feedmeup — automated news brief generator

This project pulls news from configured RSS/Atom feeds, filters items by keywords, and generates Jekyll-compatible Markdown posts which are published to GitHub Pages.

## How it works (high level)

- `fetch_news.py` — fetches feeds, filters by `config.yaml` keywords, groups similar items, and writes `_posts/YYYY-MM-DD-HH-MM-news-brief.md` files.
- `config.yaml` — where you list `sources` (name, url, category) and `filters.keywords`.
- GitHub Actions (`.github/workflows/news.yml`) — runs the script on schedule and pushes generated posts to the Pages branch.

## Where to update feeds and categories

Edit `config.yaml` in the repository root. Each source follows this format:

```yaml
sources:
  - name: Example Site
    url: https://example.com/feed.xml
    category: Security
```

When you add a new source, pick a `category` that groups similar sites (e.g., `LLM`, `Cloud`, `Security`, `Vulnerability`, `ThreatIntel`, `Regulation`).

Below is the current feed list (name — category — url). To change the feed list, open `config.yaml` and edit the `sources:` section.

-- Feed list (current `config.yaml`) --

LLM & AI Blogs
- OpenAI News — LLM — https://openai.com/news/rss.xml
- Google AI Blog — LLM — https://blog.google/technology/ai/rss/
- Microsoft AI Blog — LLM — https://blogs.microsoft.com/ai/feed/

Cloud
- AWS News — Cloud — https://aws.amazon.com/about-aws/whats-new/recent/feed/
- Azure Updates — Cloud — https://azurecomcdn.azureedge.net/en-us/updates/feed/
- Google Cloud Blog — Cloud — https://cloud.google.com/feeds/blog.xml

Security Sites
- TechRadar Pro Security — Security — https://www.techradar.com/feeds/tag/security
- Dark Reading — Security — https://www.darkreading.com/rss_simple.asp
- Krebs on Security — Security — https://krebsonsecurity.com/feed/
- The Hacker News — Security — https://feeds.feedburner.com/TheHackersNews
- BleepingComputer — Security — https://www.bleepingcomputer.com/feed/
- SC Magazine — Security — https://www.scmagazine.com/home/feed/
- SecurityWeek — Security — https://feeds.feedburner.com/securityweek
- Help Net Security — Security — https://www.helpnetsecurity.com/feed/
- Bruce Schneier Blog — Security — https://www.schneier.com/blog/atom.xml
- TheRegister — Tech — https://www.theregister.com/headlines.atom

Vulnerability & CVE feeds
- CVE Feed (High/Critical) — Vulnerability — https://cvefeed.io/rssfeed/
- CVE Details Recent — Vulnerability — https://www.cvedetails.com/vulnerability-feeds-form.php?type=rss&orderby=3&cvssscoremin=7
- Rapid7 Vulnerability Research — Vulnerability — https://blog.rapid7.com/tag/vulnerability-research/rss/
- Tenable Research — Vulnerability — https://www.tenable.com/blog/rss.xml
- VulnDB — Vulnerability — https://vuldb.com/rss.xml
- ExploitDB — Vulnerability — https://www.exploit-db.com/rss.xml
- Qualys VMDR Blog — Vulnerability — https://blog.qualys.com/feed

Threat Intelligence & Research
- Recorded Future — ThreatIntel — https://www.recordedfuture.com/feed/
- CrowdStrike Blog — ThreatIntel — https://www.crowdstrike.com/blog/feed/
- Cisco Talos — ThreatIntel — https://blog.talosintelligence.com/feeds/posts/default
- Malwarebytes Labs — ThreatIntel — https://blog.malwarebytes.com/feed/
- Palo Alto Unit 42 — ThreatIntel — https://unit42.paloaltonetworks.com/feed/
- SANS ISC — ThreatIntel — https://isc.sans.edu/rssfeed.xml
- Microsoft Security Blog — Security — https://www.microsoft.com/en-us/security/blog/feed/

Asia-Pacific regulatory & national security
- Singapore MAS — Regulation — https://www.mas.gov.sg/rss/news
- Singapore CSA — Security — https://www.csa.gov.sg/rss/news
- Japan NISC — Security — https://www.nisc.go.jp/rss/eng-news.xml
- India CERT-In — Security — https://www.cert-in.org.in/rss
- Hong Kong PCPD — Regulation — https://www.pcpd.org.hk/rss/press.xml
- Philippines NPC — Regulation — https://www.privacy.gov.ph/rss/feed.xml
- Korea KISA — Security — https://www.kisa.or.kr/rss/eng.xml
- Malaysia MyCERT — Security — https://www.mycert.org.my/rss

## How to add/remove feeds (step-by-step)

1. Open `config.yaml` and locate the `sources:` list.
2. Add a new entry using the same `name/url/category` keys.
3. Save and push the change to your repo. The next scheduled run (or manual dispatch) will pick up the new feed.

Example addition:

```yaml
- name: New Research Blog
  url: https://newsite.example/feed.xml
  category: ThreatIntel
```

If you remove a source, delete its block from `config.yaml` and push; the site will stop pulling from that feed.

## Running locally (quick)

1. Create and activate a venv (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

2. Run the script:

```powershell
python fetch_news.py
```

Check `_posts/` for generated Markdown. If you want to test CI behavior, run `pytest` or push a test commit.

## Troubleshooting

- If no posts are generated: verify `config.yaml` has `sources` and `filters.keywords` are present; inspect CI logs for feed fetch errors.
- If posts do not appear on your Pages site: confirm the workflow committed to the branch configured in GitHub Pages (commonly `gh-pages`).
- If a feed breaks formatting: add the feed but expect some summaries to be HTML; `fetch_news.py` sanitizes summaries but you can tweak `format_entries_for_category` in the script.

## Contributing / Maintenance

- Keep `requirements.txt` updated and run `pip-audit` periodically.
- Move generated posts into the Pages branch (CI should handle this). Do not keep generated posts committed on your main branch — they are now in `.gitignore`.

---

If you want I can commit this README update directly; say "apply README changes" and I'll push the file for you.
