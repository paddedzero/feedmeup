# Migration to Official GitHub Actions Deployment

**Date**: January 4, 2026  
**Status**: Ready for Testing  
**Type**: Deployment Strategy Change

---

## What Changed

### ❌ **OLD METHOD** (Hybrid - Manual Push to gh-pages)
```yaml
- Build with Jekyll 4.4.1
- Capture _site/ to /tmp/
- git checkout gh-pages
- Copy files manually
- git add + git commit + git push
- GitHub Pages serves gh-pages branch
```

**Problems**:
- Complex blue-green deployment logic
- Manual git operations error-prone
- Still tries to use gh-pages branch
- GitHub Pages tried to rebuild with Jekyll 3.10.0 (incompatible!)

### ✅ **NEW METHOD** (Official GitHub Actions Deployment)
```yaml
- Build with Jekyll 4.4.1
- actions/configure-pages@v4
- actions/upload-pages-artifact@v3 (packages _site/)
- actions/deploy-pages@v4 (deploys directly)
```

**Benefits**:
- ✅ Official, supported method
- ✅ No manual git operations
- ✅ No gh-pages branch needed
- ✅ Simpler, fewer failure points
- ✅ Automatic .nojekyll handling

---

## Changes Required

### 1. Workflow File ✅ **DONE**

**File**: `.github/workflows/news.yml`

**What Changed**:
- ✅ Added `concurrency` group to prevent overlapping deployments
- ✅ Changed permissions: removed `contents: write`, kept `pages: write`, `id-token: write`
- ✅ Split into two jobs: `build` and `deploy`
- ✅ Replaced entire manual deployment with 3 official actions
- ✅ Removed ~120 lines of complex blue-green logic

**New Structure**:
```yaml
jobs:
  build:
    - Checkout
    - Setup Ruby
    - Setup Python
    - Install dependencies
    - Run fetch_news.py
    - Build Jekyll
    - Setup Pages
    - Upload artifact
    
  deploy:
    needs: build
    - Deploy to Pages
```

### 2. GitHub Pages Settings ⚠️ **MANUAL STEP REQUIRED**

**You must change this setting**:

1. Go to: **https://github.com/paddedzero/feedmeup/settings/pages**
2. Under **"Build and deployment"** → **"Source"**
3. Change from: **"Deploy from a branch: gh-pages"**
4. Change to: **"GitHub Actions"**
5. Click **Save**

**Screenshot guide**:
```
┌─────────────────────────────────────┐
│ Build and deployment                │
├─────────────────────────────────────┤
│ Source: [GitHub Actions ▼] ← SELECT │
│                                      │
│ Old: Deploy from a branch           │
│ New: GitHub Actions                 │
└─────────────────────────────────────┘
```

### 3. gh-pages Branch ℹ️ **OPTIONAL**

**Current Status**: Has old deployments from hybrid method

**Options**:
- **Option A**: Delete it (clean slate)
  ```bash
  git push origin --delete gh-pages
  ```
- **Option B**: Keep it (as history/backup)
  - Actions won't use it
  - Won't interfere with new deployment

**Recommendation**: Keep it for now, delete after verifying new method works

---

## Testing Steps

### Phase 1: Initial Deployment Test

1. ✅ Commit workflow changes to main
   ```bash
   git add .github/workflows/news.yml
   git commit -m "BREAKING: Migrate to official GitHub Actions deployment"
   git push origin main
   ```

2. ⚠️ **CRITICAL**: Change Pages settings to "GitHub Actions" (see section 2)

3. ✅ Manually trigger workflow
   - Go to: Actions → Weekly News Brief
   - Click "Run workflow" → "Run workflow"

4. ✅ Monitor workflow
   - Should complete in ~3-5 minutes
   - Check for errors in Actions tab

5. ✅ Verify deployment
   - Visit: https://paddedzero.github.io/feedmeup
   - Check: Sidebar tabs visible
   - Check: Dark mode works
   - Check: Recent posts displayed

### Phase 2: Validation Checklist

After workflow completes:

- [ ] Workflow shows green checkmark
- [ ] "build" job completed successfully
- [ ] "deploy" job completed successfully
- [ ] Site loads at https://paddedzero.github.io/feedmeup
- [ ] Chirpy theme styling visible
- [ ] Sidebar navigation tabs present (CATEGORIES, TAGS, ARCHIVES, ABOUT)
- [ ] Dark mode toggle works
- [ ] RSS feed accessible (https://paddedzero.github.io/feedmeup/feed.xml)
- [ ] Recent posts display correctly
- [ ] No "Could not find theme" errors

### Phase 3: Verify No Jekyll Rebuild Errors

Previously we saw this error:
```
The jekyll-theme-chirpy theme could not be found.
```

**This should NOT appear anymore** because:
- We're deploying pre-built `_site/` (Jekyll 4.4.1 already ran)
- GitHub Pages serves it directly (no rebuild)
- No conflict with GitHub Pages' Jekyll 3.10.0

---

## Rollback Plan

If new deployment fails:

### Quick Rollback (5 minutes)
1. Go to Pages settings
2. Change source back to: "Deploy from a branch: gh-pages"
3. Old gh-pages content will be served immediately
4. Investigate issue without pressure

### Revert Workflow (if needed)
```bash
# Find previous working commit
git log --oneline | grep -i deploy

# Revert to that commit
git revert <commit-hash>
git push origin main
```

---

## Technical Comparison

| Aspect | Old Method | New Method |
|--------|-----------|------------|
| **Workflow complexity** | ~200 lines | ~100 lines |
| **Manual git operations** | Yes (checkout, commit, push) | No |
| **Failure points** | Many (branch switch, backup, validation, push) | Few (build, upload, deploy) |
| **Rollback complexity** | Manual (restore from backup) | Automatic (Actions handles it) |
| **Branch management** | Requires gh-pages branch | No branches needed |
| **Permissions** | `contents: write` (dangerous) | Only `pages: write` |
| **Official support** | No (custom solution) | Yes (official Actions) |
| **Jekyll version control** | Must use .nojekyll trick | Handled automatically |

---

## Why This Fixes The Error

### The Error We Had
```
The jekyll-theme-chirpy theme could not be found.
github-pages 232 | Error: The jekyll-theme-chirpy theme could not be found.
```

### Root Cause
1. We removed `.nojekyll` → told GitHub Pages to rebuild
2. GitHub Pages uses Jekyll 3.10.0 (we need 4.4.1)
3. Chirpy requires Jekyll 4.4.1+
4. GitHub Pages couldn't install Chirpy → build failed

### How Official Actions Fix This
1. We build with Jekyll 4.4.1 in Actions ✅
2. `upload-pages-artifact` packages complete `_site/` ✅
3. `deploy-pages` deploys pre-built site ✅
4. GitHub Pages serves HTML directly (no rebuild) ✅
5. `.nojekyll` handled automatically by Actions ✅

**Result**: No Jekyll version conflict, no theme errors

---

## Migration Timeline

| Time | Action | Who |
|------|--------|-----|
| ✅ **Now** | Workflow updated | Done |
| ⏳ **Next** | Change Pages settings | You (manual) |
| ⏳ **Next** | Test deployment | You (trigger workflow) |
| ⏳ **+5 min** | Verify live site | You (check URL) |
| ⏳ **+1 day** | Monitor stability | Both |
| ⏳ **+1 week** | Delete gh-pages branch | Optional |

---

## Expected Outcomes

### Immediate (After First Deployment)
- ✅ No Jekyll theme errors
- ✅ Sidebar tabs visible
- ✅ Chirpy theme fully working
- ✅ Simpler workflow logs

### Long-term
- ✅ Fewer deployment failures
- ✅ Easier to debug (official tools)
- ✅ Less maintenance (no manual git)
- ✅ Better performance (optimized Actions)

---

## Support & Troubleshooting

### If Workflow Fails

1. **Check Actions logs**:
   - Go to: Actions → Select failed run
   - Expand failed step
   - Copy error message

2. **Common issues**:
   - Pages settings not changed → Change to "GitHub Actions"
   - Permissions insufficient → Check repo settings
   - Jekyll build failed → Check local build first

3. **Verify local build**:
   ```bash
   bundle exec jekyll build
   ls _site/index.html  # Should exist
   ```

### If Site Doesn't Update

1. **Check deployment completed**: Actions → Should show green
2. **Wait 1-2 minutes**: CDN propagation delay
3. **Hard refresh**: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
4. **Check URL**: Ensure using correct URL (paddedzero.github.io/feedmeup)

### If Tabs Still Missing

1. **Check `_site/` locally**:
   ```bash
   grep -r "real tabs" _site/*.html
   # Should show tab items, not empty
   ```

2. **Verify build includes tabs**:
   ```bash
   ls _site/categories/ _site/tags/ _site/archives/
   # Directories should exist
   ```

3. **Check Chirpy CSS loading**:
   - Open browser DevTools (F12)
   - Network tab → Filter CSS
   - Should see chirpy CSS files loading

---

## Documentation Updates Needed

After successful migration:

- [ ] Update README.md with new deployment method
- [ ] Update LESSONS_LEARNED.md with migration experience
- [ ] Document official deployment in PROJECT_SPEC.md
- [ ] Update copilot-instructions.md with correct workflow
- [ ] Archive old deployment docs

---

## Questions?

**Q: Will old gh-pages content be lost?**  
A: No, it's preserved in the branch. Can keep as backup.

**Q: Can I switch back to old method?**  
A: Yes, just change Pages settings back to "Deploy from branch: gh-pages"

**Q: What if I forget to change Pages settings?**  
A: Workflow will fail with clear error message. Just change setting and re-run.

**Q: Do I need to update anything else?**  
A: No, just the Pages setting. Everything else is in the workflow.

**Q: How do I know it worked?**  
A: Site loads + tabs visible + no theme errors in Actions logs

---

**Status**: ✅ Ready for testing  
**Next Action**: Change Pages settings to "GitHub Actions"  
**Expected Result**: Clean deployment, no theme errors, sidebar tabs visible
