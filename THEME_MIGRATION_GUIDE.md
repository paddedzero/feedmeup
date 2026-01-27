# Migrating from Gem-Based to Local Chirpy Theme

## Current Setup
- **Type**: Gem-based remote theme
- **Source**: RubyGems package `jekyll-theme-chirpy` v7.4.1
- **Limitation**: Cannot directly edit theme files (layouts, includes, assets)

## Migration Options

### Option 1: Full Local Theme (Complete Control)

**Steps:**

1. **Download Chirpy theme source**
   ```bash
   # Download the exact version you're using
   curl -L https://github.com/cotes2020/jekyll-theme-chirpy/archive/refs/tags/v7.4.1.zip -o chirpy-theme.zip
   
   # Or use git
   git clone --branch v7.4.1 --depth 1 https://github.com/cotes2020/jekyll-theme-chirpy.git temp-chirpy
   ```

2. **Copy theme files into your repo**
   Copy these directories from the theme into your repo root:
   - `_layouts/` - All layout files
   - `_includes/` - All include files  
   - `_sass/` - All stylesheet files
   - `assets/` - All theme assets (merge with your existing assets/)
   - `_plugins/` - Any theme plugins
   - `_data/` - Theme data files (merge with your existing _data/)

3. **Update Gemfile**
   Remove the theme gem and add Jekyll directly:
   ```ruby
   # Remove this line:
   # gem "jekyll-theme-chirpy", "~> 7.4", ">= 7.4.1"
   
   # Add these instead:
   gem "jekyll", "~> 4.3"
   gem "jekyll-paginate"
   gem "jekyll-redirect-from"
   gem "jekyll-seo-tag"
   gem "jekyll-archives"
   gem "jekyll-sitemap"
   # ... add any other Chirpy dependencies
   ```

4. **Update _config.yml**
   Remove the theme declaration:
   ```yaml
   # Remove this if it exists:
   # theme: jekyll-theme-chirpy
   ```

5. **Run bundle install**
   ```bash
   bundle install
   ```

**Pros:**
- ✅ Full control over all theme files
- ✅ Can edit layouts, includes, styles directly
- ✅ No more workarounds like JavaScript injection
- ✅ Can customize anything

**Cons:**
- ❌ Harder to update theme (manual merge required)
- ❌ Larger repo size
- ❌ More files to maintain

---

### Option 2: Selective Override (Hybrid Approach - Current + Override)

Keep the gem theme but override only specific files you need to edit.

**Steps:**

1. **Keep current Gemfile** (no changes needed)

2. **Create local overrides** by copying only the files you want to customize:
   ```bash
   # For example, to customize the home layout:
   mkdir -p _layouts
   curl -o _layouts/home.html https://raw.githubusercontent.com/cotes2020/jekyll-theme-chirpy/v7.4.1/_layouts/home.html
   ```

3. **Edit the local file** - Your local `_layouts/home.html` will override the gem version

**Pros:**
- ✅ Smaller repo size
- ✅ Easy theme updates (just update gem version)
- ✅ Only customize what you need

**Cons:**
- ❌ Can conflict with theme updates
- ❌ Need to track which files are overridden
- ❌ May break on theme version updates

---

## Recommended Approach for Your Use Case

Since you want to:
- Add a banner to the home page
- Have full control over layout customization

**I recommend Option 2** (Selective Override) with these specific files:

### Files to Override:
1. `_layouts/home.html` - Add `{{ content }}` support
2. `_includes/head-custom.html` - Already customized for banner injection

### Steps to Implement:

1. Create the layouts directory and override home.html:
   ```bash
   mkdir _layouts
   curl -o _layouts/home.html https://raw.githubusercontent.com/cotes2020/jekyll-theme-chirpy/v7.4.1/_layouts/home.html
   ```

2. Edit `_layouts/home.html` to add `{{ content }}` before the post list (around line 49):
   ```liquid
   {% endfor %}
   {% endif %}
   
   {{ content }}  <!-- Add this line -->
   
   <div id="post-list" class="flex-grow-1 px-xl-1">
   ```

3. Update `index.html` to include your banner directly in the front matter content

4. Remove the JavaScript workaround (`inject-banner.js`) since it won't be needed

This gives you the customization you need without the overhead of maintaining the entire theme locally.

---

## Migration Checklist

- [ ] Decide on migration approach (Option 1 or 2)
- [ ] Backup your current site
- [ ] Download/copy required theme files
- [ ] Update Gemfile (if Option 1)
- [ ] Update _config.yml (if Option 1)
- [ ] Test build locally
- [ ] Update GitHub Actions workflow if needed
- [ ] Deploy and verify
- [ ] Document which files are overridden

---

## Notes

- Your current `_includes/head-custom.html` is already a local override
- Your current `assets/js/inject-banner.js` is a workaround that won't be needed with Option 2
- Theme version: v7.4.1 (locked)
- Current build: GitHub Actions with Ruby/Jekyll
