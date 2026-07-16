# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`pub-blog` is the **private source repo** for themissingsunday.com, an Astro-based personal blog with an
automated weekly tech-news aggregation pipeline bolted on. It has two halves that share one Astro site:

1. **The Astro/Svelte site** (`src/`, `site/`) — a personal blog with manual posts, a projects page, an
   "appearances" collection, and a `newsfeed` collection that is *generated*, not hand-written.
2. **The news pipeline** (`scripts/fetch_news.py` + `scripts/config.yaml`) — a Python script that fetches
   40+ RSS feeds, filters/dedups/scores them, calls Gemini for summarization, and writes Markdown posts
   straight into `site/content/newsfeed/`.

A third piece, `scripts/sanitize_for_distribution.py`, exists because this repo also doubles as the
"secret sauce" repo: a GitHub Actions workflow strips out the pipeline internals (scripts, config,
caches, drafts) and mirror-pushes a public-safe copy of the built site to a **separate public repo**,
`paddedzero/feedmeup`. Never assume `pub-blog` and `feedmeup` are the same repo — `feedmeup` is a
generated distribution target, not something to edit directly.

**Root-level docs are stale, not source of truth.** `README.md`, `.github/PROJECT_SPEC.md`, and
`.github/copilot-instructions.md` describe an old Jekyll/Chirpy/`gh-pages`/`_posts` architecture that this
repo has since migrated away from (now Astro + `site/content/newsfeed/` + GitHub Actions Pages deploy).
Don't trust those files for how the site currently builds or deploys — trust `astro.config.mjs`,
`src/content.config.ts`, and the workflows in `.github/workflows/`. `.github/LESSONS_LEARNED.md` is
historical incident context (a Jekyll-era gh-pages deletion + broken-theme saga) — useful for the "don't
skip validation, don't force-push blind" mindset, not for current deployment mechanics.

## Commands

### Astro site (Node/npm)
```
npm run dev          # astro dev — local dev server
npm run build         # astro build — production build to dist/
npm run preview       # astro preview — serve the production build locally
npm run check         # astro check — type-check .astro files + TS
```
There is no JS/TS test suite or linter configured — `astro check` (which also runs `svelte-check` via the
Astro/Svelte integration) is the only automated correctness gate for the frontend.

### News pipeline (Python)
```
python -m venv .venv && .venv\Scripts\Activate.ps1   # Windows venv
pip install -r requirements.txt
$env:GEMINI_API_KEY="..."                              # required for AI summarization/analysis
python scripts/fetch_news.py                           # runs the full pipeline, writes into site/content/newsfeed/
```
Ad hoc test/debug scripts (not a real pytest suite — run individually):
```
python scripts/test_dedup.py
python test_negative_keywords.py
python test_tagging_dashboard.py
python test_regex.py
python validate_filtering.py
pytest tests/          # only if a tests/ dir exists; there isn't one checked in currently
```

### Distribution sync (rarely run manually — normally triggered by CI)
```
python scripts/sanitize_for_distribution.py   # builds temp_dist/, 12-point safety validation, aborts on any leak
```

## Architecture

### Content collections (`src/content.config.ts`)
Five Astro content collections, each a `glob()` loader over `site/content/<name>/`: `posts` (manual blog
posts), `newsfeed` (pipeline-generated), `projects`, `appearances`, `about`. `posts` and `newsfeed` share
almost the same schema (title/description/pubDate/tags/series/translatedPosts/etc.) — when changing one
schema, check whether the other needs the same change, since they're rendered through mostly-shared UI
(`PostCard.svelte`, `src/lib/utils/posts.ts` has parallel `getPublishedPosts`/`getPublishedNewsfeed`
helpers that both filter out `draft: true`).

Path aliases (`tsconfig.json` + `astro.config.mjs` vite alias): `@/config` → `site/config.ts`, `@/*` and
`~/*` → `src/*`, `$lib` → `src/lib`. Site-wide settings (title, base path, comments/giscus config, hero/CTA
toggles) live in `site/config.ts`, not in `astro.config.mjs`.

### News pipeline (`scripts/fetch_news.py`, ~3.3k lines, single file)
Linear pipeline driven by `main()`, roughly: load `scripts/config.yaml` → fetch all feeds in parallel
(`fetch_feed_entries`, retry/backoff session) → keyword + negative-keyword filtering
(`compile_keywords_pattern`, `matches_negative_keywords`) → dedup (fuzzy title match via RapidFuzz in
`group_similar_entries`/`consolidate_similar_entries`, plus semantic similarity via sentence-transformers)
→ scoring/tagging (`calculate_story_score`, `extract_article_tags`, source-tier weighting) → two Gemini-
generated post types:
- **Weekly Scan** (`create_weekly_scan_post`) — categorized roundup + highlights + trending-topics
  dashboard, uses `gemini-2.5-flash` for cheap per-article summaries.
- **Analyst Opinion** (`create_analyst_opinion_post`) — single "article of the week" with a deeper,
  multi-prompt Gemini analysis (technical deep-dive, threat intel, defense strategy) plus historical
  context pulled from past posts (`find_historical_context`, 12-week lookback).

Output goes through `write_dual_output()` into `site/content/newsfeed/` as Astro-collection Markdown with
front matter; failed feeds get a Markdown error post in `site/content/errors/` instead of crashing the run
(`save_error_post`). State that persists across runs lives in `.article_registry/` (cross-run dedup) and
`.feed_cache/` (per-feed fetch cadence) — both are private/gitignored and excluded from the public
distribution.

All HTML fragments written into generated Markdown (article titles, summaries, source names, error
messages) must be passed through `html.escape()` / the existing `_render_source_list_html` /
`clean_summary` helpers before being embedded — this repo had a real XSS-via-RSS-content issue here
(see `ARCHITECTURE_REVIEW.md`), so any new HTML-emitting code path in `fetch_news.py` needs the same
treatment.

### GitHub Actions (`.github/workflows/`)
Three independent workflows, not one pipeline:
- `news-generate.yml` — Monday 08:00 UTC (or manual dispatch), runs `fetch_news.py`, commits any new
  `site/content/newsfeed/` / `site/content/errors/` files straight to `main`.
- `news-push.yml` — triggered by `news-generate.yml` completing (or manual dispatch), runs
  `sanitize_for_distribution.py` and force-pushes `temp_dist/` to the separate public `feedmeup` repo via
  `FEEDMEUP_PAT`. Treat changes to the exclusion lists in `sanitize_for_distribution.py` as high-risk —
  its whole job is to be the last line of defense against leaking `scripts/`, API keys, or `.env` files to
  a public repo.
- `deploy.yml` — on push to `main`, builds the Astro site (`npm ci && npm run build`) and deploys `dist/`
  to GitHub Pages for `pub-blog` itself.

### Content lifecycle
`site/content/_drafts/` (if present) is excluded from public distribution by folder convention — draft
detection is path-based, not a frontmatter flag alone. When adding new "private" content or data, prefer
extending the denylist in `sanitize_for_distribution.py` over trusting a frontmatter field, since that
script is what actually gates what leaves the repo.
