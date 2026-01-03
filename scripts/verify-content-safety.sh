#!/bin/bash
# CRITICAL: Content Safety Verification Script
# This script MUST run before any destructive git operations
# Fails immediately if user content is missing

set -e

echo "🔐 CONTENT SAFETY CHECK"
echo "======================="

# Critical user content that MUST exist
CRITICAL_DIRS=("_posts" "assets" "_data")
CRITICAL_FILES=("_config.yml" "README.md")

ERRORS=0

# Check directories
for dir in "${CRITICAL_DIRS[@]}"; do
  if [ ! -d "$dir" ]; then
    echo "❌ CRITICAL: Directory missing: $dir"
    ERRORS=$((ERRORS+1))
  else
    COUNT=$(find "$dir" -type f | wc -l)
    echo "✅ $dir exists ($COUNT files)"
  fi
done

# Check files
for file in "${CRITICAL_FILES[@]}"; do
  if [ ! -f "$file" ]; then
    echo "❌ CRITICAL: File missing: $file"
    ERRORS=$((ERRORS+1))
  else
    echo "✅ $file exists"
  fi
done

# Special check: _posts must have markdown files
if [ -d "_posts" ]; then
  POST_COUNT=$(find _posts -name "*.md" -type f | wc -l)
  if [ "$POST_COUNT" -eq 0 ]; then
    echo "❌ CRITICAL: _posts directory exists but contains NO markdown files!"
    ERRORS=$((ERRORS+1))
  else
    echo "✅ _posts contains $POST_COUNT markdown files"
  fi
fi

# FAIL if any checks failed
if [ $ERRORS -gt 0 ]; then
  echo ""
  echo "🚨 SAFETY CHECK FAILED"
  echo "User content is missing or incomplete!"
  echo "Do NOT proceed with destructive operations."
  exit 1
fi

echo ""
echo "✅ ALL SAFETY CHECKS PASSED"
echo "Safe to proceed with git operations."
exit 0
