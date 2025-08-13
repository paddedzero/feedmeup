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

### 🛠 Files You’ll Edit

* **`config.yaml`** → Change:

  * `keywords`: Add/remove topics you care about
  * `sources`: Add/remove RSS/news feeds
* **`fetch_news.py`** → Adjust:

  * How summaries are generated
  * How many headlines to pull
* **`_config.yml`** (Jekyll) → Change:

  * Site title, description, theme

---

### 🚀 How to Run Locally

```bash
python fetch_news.py
```

This will:

* Pull fresh headlines
* Create new `_posts/YYYY-MM-DD-news.md` files

Commit and push manually if you’re testing:

```bash
git add .
git commit -m "Update news feed"
git push
```

---

### 📅 Automation

* GitHub Actions (`news.yml`) runs automatically on your schedule (set in the workflow file).
* No manual Git commands needed after setup — your site updates itself.

---

If you like, I can now **write this `config.yaml` for you pre-filled with the cybersecurity, AI, cloud, and APAC regulatory feeds and keywords** we discussed earlier, so you can just edit it later instead of building it from scratch.

Do you want me to create that ready-to-use config for you?
