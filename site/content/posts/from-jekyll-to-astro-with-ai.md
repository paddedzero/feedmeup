---
title: "From Jekyll to Astro — How I Rebuilt My Site with AI in Days, Not Months"
description: "A practical walkthrough of migrating a GitHub Pages site from Jekyll to Astro, using GitHub Copilot and Gemini to build a fully automated news aggregation engine along the way."
pubDate: 2026-02-07
tags: ["astro", "jekyll", "github-pages", "ai", "copilot", "gemini", "migration", "tutorial"]
featured: true
---

> *Back in 2020, I wrote about [setting up a Jekyll site on GitHub Pages](/feedmeup/posts/welcome-to-unlocked-today). That post covered forking a theme, editing `_config.yaml`, and writing your first Markdown post. It took me a few weekends to get comfortable. Fast forward to 2026 — I rebuilt the entire site on Astro, added a 140+ source news aggregation engine with AI summarization, and deployed it in a fraction of the time. The difference? AI pair programming.*

----

This is not a "look how smart AI is" post. This is a practical account of what actually happened when I decided to move off Jekyll, what worked, what broke, and how tools like GitHub Copilot and Google Gemini changed my workflow in ways I did not expect.

## Why Leave Jekyll?

Jekyll served me well for five years. It is simple, it works with GitHub Pages out of the box, and Markdown is still the best way to write. But a few things started bothering me:

- **Build speed.** Jekyll builds got slower as content grew. Ruby dependencies occasionally broke after updates.
- **Component limitations.** I wanted interactive elements — search, theme toggles, table of contents — without hacking Liquid templates.
- **Modern tooling.** The JavaScript ecosystem moved on. Frameworks like Astro offer static-first architecture with component islands for interactivity when you need it.

I did not want to lose what Jekyll gave me — Markdown content, GitHub Pages hosting, simple deploys. I just wanted more.

## The Stack I Landed On

- **Astro** — static site generator, content collections, file-based routing
- **Svelte** — interactive components (search, theme toggle, audio player)
- **Tailwind CSS** — styling without fighting CSS specificity
- **GitHub Actions** — CI/CD for builds and automated content
- **Python** — news aggregation engine (RSS parsing, web scraping, deduplication)
- **Google Gemini** — AI summarization and analyst opinion generation
- **GitHub Copilot** — pair programming for everything above

## Contents

- Step 1 — Set up the Astro project
- Step 2 — Migrate content from Jekyll
- Step 3 — Build the news aggregation engine
- Step 4 — Add AI summarization with Gemini
- Step 5 — Split workflows for generate and distribute
- Step 6 — Deploy to GitHub Pages
- What I learned

## Step 1 — Set up the Astro project

The first thing I did was scaffold a new Astro project. If you are coming from Jekyll, the mental model is similar — you write Markdown, it generates static HTML. The difference is that Astro uses a `src/pages/` directory for routes and `site/content/` for content collections with schema validation.

```bash
npm create astro@latest
```

From there, Copilot handled most of the boilerplate. I described the layout I wanted — a header with navigation, a hero section with a profile photo, a posts listing page, and a newsfeed page — and Copilot generated the Astro components. Things that would have taken me hours of reading Astro docs took minutes of iterating with Copilot in VS Code.

The key architectural decision was separating **content** from **code**. All my Markdown lives in `site/content/` with typed schemas defined in `content.config.ts`. This means if a post is missing a required field like `pubDate`, the build fails immediately instead of silently rendering broken pages. Jekyll never gave me that safety net.

## Step 2 — Migrate content from Jekyll

Migrating posts from Jekyll to Astro was straightforward. The frontmatter format is nearly identical — just rename `date` to `pubDate` and adjust the schema. I wrote a small migration script to handle the conversion:

```python
# scripts/migrate_posts.py — bulk convert Jekyll frontmatter to Astro format
```

The images were the tedious part. Jekyll stores images relative to the site root. Astro with its `<Image>` component wants them imported as modules for optimization. I moved everything to `site/assets/` and set up a path alias (`@/site-assets`) in the Astro config so imports stay clean.

The old Jekyll post referenced images like `/feedmeup/images/2020-07-26/signup-github.png`. These still work because Astro serves the `public/` directory as-is. No broken links.

## Step 3 — Build the news aggregation engine

This is where the project went from "migrate a blog" to "build something genuinely useful." I wanted an automated weekly news digest covering cybersecurity, AI, cloud, and regulatory topics from across the Asia-Pacific region.

The engine — `fetch_news.py` — grew to about 3,200 lines of Python. Here is what it does:

1. **Fetches 140+ sources** — RSS feeds, Atom feeds, and 10 custom web scrapers for sites without RSS (CISA, MSRC, CERT-In, Singapore CSA, and others)
2. **Filters by keywords** — 270 terms after synonym expansion across 30 groups (vulnerability types, threat actors, malware families, compliance terms)
3. **Deduplicates** — fuzzy title matching with per-category thresholds (stricter for CVEs at 0.92, relaxed for AI opinion pieces at 0.75)
4. **Groups similar stories** — multi-source consolidation shows when 5 outlets cover the same breach, with an expandable source list
5. **Ranks by recency** — breaking news under 6 hours gets a 3x boost, same-day stories get 2x
6. **Respects domain diversity** — 4-tier system caps how many articles per source (government CERTs get 999, vendor blogs get 3, personal blogs get 1)

Building this without AI would have taken weeks of trial and error. With Copilot, I described each feature — "add fuzzy deduplication with per-category thresholds" — and iterated on the generated code. Copilot understood the existing codebase context, so each addition fit naturally into the existing patterns.

For the web scrapers, the challenge was that each site has a different structure. CISA uses a KEV JSON API. Microsoft MSRC exposes a CVRF REST API. Packet Storm is fully JavaScript-rendered. Copilot helped generate the initial scraper class for each site, and I refined the selectors and error handling from there. Ten site-specific scrapers in about 760 lines.

## Step 4 — Add AI summarization with Gemini

Raw RSS summaries are often useless — truncated HTML, marketing copy, or just the first paragraph. I integrated Google Gemini to generate two types of content:

- **JIT excerpts** — short, factual one-line summaries generated inline as articles are processed (150 max tokens, using `gemini-2.5-flash`)
- **Analyst opinions** — weekly editorial synthesis across all collected articles, identifying trends, connecting dots, and highlighting what matters (3,000 max tokens, using `gemini-2.5-flash`)

The key design decision was **keeping token costs low**. The multi-source consolidation feature — which shows when multiple outlets report the same story — reuses existing Gemini excerpts instead of generating new consensus summaries. Zero additional API calls for that feature.

Keyword synonym expansion was another Gemini-adjacent improvement. Instead of manually listing every variation of security terms, I built a synonym map with 30 groups. The matching engine uses word-boundary regex so "data breach" correctly expands to include "breach notification" and "data leak," but "breach" alone does not trigger on "breaching whale" (yes, that was a real false-positive I had to fix).

## Step 5 — Split workflows for generate and distribute

The deployment architecture evolved as the project grew. Initially everything ran in a single GitHub Actions workflow. That meant if I just wanted to push a content update — like a new profile photo or a blog post — it would regenerate all the news articles too. Wasteful.

I split it into three workflows:

| Workflow | Trigger | Purpose |
|---|---|---|
| **Generate News Content** | Monday 08:00 UTC / manual | Runs the aggregation engine, commits posts |
| **Push to feedmeup** | Auto after generate / manual | Sanitizes and pushes to the public repo |
| **Deploy to GitHub Pages** | On push to main | Builds Astro site, deploys to Pages |

The `Push to feedmeup` workflow can be triggered independently. So when I update the profile photo, change the about page, or publish a manual post like this one, I just run the push workflow. No regeneration. The sanitization script strips everything private — the Python scripts, config files, API keys, draft posts — before pushing to the public `feedmeup` repository.

This separation also made the private/public repo split clean. The engine repo (`pub-blog`) stays private. The published site (`feedmeup`) stays public. The PAT-authenticated push action bridges them.

## Step 6 — Deploy to GitHub Pages

Deploying Astro to GitHub Pages is simpler than Jekyll in some ways. No Ruby. No Bundler. Just:

```bash
npm ci
npm run build
```

The `deploy.yml` workflow uses the official GitHub Pages actions to upload the built `dist/` directory. It triggers on every push to main, so any commit — whether from the news generator or a manual edit — automatically rebuilds and deploys the site.

One thing that caught me off guard was the per-category lookback window. Regulatory sources from APAC — Singapore MAS, Hong Kong PCPD, Philippines NPC — publish infrequently. A 7-day lookback missed most of their updates. I added a `category_lookback_days` config so Cyber Regulatory sources get a 28-day window while everything else stays at 7 days.

## What I learned

**AI pair programming is not autopilot.** Copilot and Gemini did not build this for me. They accelerated the parts that would have been slow — boilerplate, regex patterns, scraper selectors, component scaffolding. The architectural decisions — how to structure deduplication, when to consolidate sources, how to keep token costs down — those were still mine to make.

**The biggest AI wins were in the boring parts.** Writing 10 site-specific scrapers. Expanding 30 synonym groups. Generating responsive image components. Debugging CSS specificity. These are the tasks that eat hours and produce no creative satisfaction. Offloading them to AI freed me to focus on the system design.

**Schema validation saves you from yourself.** Astro's typed content collections caught errors that Jekyll would have silently swallowed. A missing `pubDate`, a malformed tag array, a draft flag set to a string instead of boolean — all caught at build time.

**Start simple, then split.** The single workflow file worked fine until it didn't. The split into generate, push, and deploy happened naturally when the pain of unnecessary regeneration became real. Do not over-engineer your CI/CD on day one.

**Keep your costs visible.** Every Gemini API call has a token cost. By designing the consolidation feature to reuse existing excerpts instead of generating new ones, I avoided an estimated 43,000 extra tokens per week. Small decisions compound.

## Compared to 2020

In 2020, setting up Jekyll took me a few weekends of learning Git, Markdown, Liquid templates, and Ruby gems. The result was a static blog.

In 2026, the migration to Astro plus building a full news aggregation platform with 140+ sources, AI summarization, web scrapers, and automated deployment took a similar amount of calendar time — but produced something fundamentally more capable. The difference is not that I got faster. The tools got dramatically better at handling the parts that used to slow me down.

If you are still on Jekyll and it works for you, keep using it. But if you are hitting its limits — build speed, interactivity, modern tooling — Astro with AI-assisted development is worth the switch. The migration path is gentler than you think.

Thats it.
