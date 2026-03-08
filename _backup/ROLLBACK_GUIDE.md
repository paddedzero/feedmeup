# Emergency Rollback Guide

## Quick Rollback (5 minutes)

### Scenario 1: gh-pages deployment is broken
```bash
git fetch origin
git checkout gh-pages
git reset --hard backup/pre-chirpy-tab-fix-2026-01-03
git push origin gh-pages --force-with-lease
```
Wait 2-5 minutes for GitHub Pages to rebuild.

### Scenario 2: main branch has issues
```bash
git checkout main
git reset --hard 9ad7ea857ad7a61d7abf6b3c3e0c422ba477ff92
git push origin main --force-with-lease
```

### Scenario 3: Need to revert specific file
```bash
# Restore _data/locales/en.yml from backup
git checkout backup/pre-chirpy-tab-fix-2026-01-03 -- _data/locales/en.yml
git commit -m "Revert locale changes"
git push
```

## Backup Branches
- `backup/pre-chirpy-tab-fix-2026-01-03` - Snapshot before locale file addition
- `main@9ad7ea857ad7a61d7abf6b3c3e0c422ba477ff92` - Last known good main branch

## Contact
If rollback fails, contact: paddedzero
