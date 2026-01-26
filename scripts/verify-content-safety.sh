#!/bin/bash
# CRITICAL: Comprehensive Content Safety Verification
# Checks ALL user-created and custom content, not just posts
# This is the "blue" state before green deployment

set -e

echo "🔐 COMPREHENSIVE CONTENT SAFETY CHECK"
echo "====================================="

# User content directories (custom files that must be preserved)
USER_DIRS=(
  "_posts"          # User blog posts
  "_tabs"           # Custom navigation tabs (Home, About, etc)
  "assets/img"      # Custom images and logo
)

# User configuration and custom files
USER_FILES=(
  "_config.yml"     # Main Jekyll config (user customized)
  "README.md"       # Project documentation
)

# Optional user content (warn if missing, don't fail)
OPTIONAL_CONTENT=(
  "assets/img/avatar.svg"    # User logo
)

ERRORS=0
WARNINGS=0

echo "Checking user content directories..."
for dir in "${USER_DIRS[@]}"; do
  if [ ! -d "$dir" ]; then
    echo "❌ CRITICAL: User directory missing: $dir"
    ERRORS=$((ERRORS+1))
  else
    COUNT=$(find "$dir" -type f 2>/dev/null | wc -l)
    if [ "$COUNT" -eq 0 ]; then
      echo "⚠️  WARNING: $dir exists but is EMPTY"
      WARNINGS=$((WARNINGS+1))
    else
      echo "✅ $dir exists ($COUNT user files)"
    fi
  fi
done

echo ""
echo "Checking user configuration files..."
for file in "${USER_FILES[@]}"; do
  if [ ! -f "$file" ]; then
    echo "❌ CRITICAL: User file missing: $file"
    ERRORS=$((ERRORS+1))
  else
    SIZE=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "?")
    echo "✅ $file exists"
  fi
done

echo ""
echo "Checking optional user content..."
for file in "${OPTIONAL_CONTENT[@]}"; do
  if [ ! -f "$file" ]; then
    echo "⚠️  OPTIONAL missing: $file (non-critical)"
    WARNINGS=$((WARNINGS+1))
  else
    echo "✅ $file exists"
  fi
done

# CRITICAL: _posts must have markdown files
echo ""
echo "Validating _posts content..."
if [ -d "_posts" ]; then
  POST_COUNT=$(find _posts -name "*.md" -type f 2>/dev/null | wc -l)
  if [ "$POST_COUNT" -eq 0 ]; then
    echo "❌ CRITICAL: _posts/ exists but contains NO markdown files!"
    ERRORS=$((ERRORS+1))
  else
    echo "✅ _posts contains $POST_COUNT markdown files"
  fi
fi

# CRITICAL: _tabs must have navigation files
echo ""
echo "Validating _tabs content..."
if [ -d "_tabs" ]; then
  TAB_COUNT=$(find _tabs -name "*.md" -type f 2>/dev/null | wc -l)
  if [ "$TAB_COUNT" -eq 0 ]; then
    echo "⚠️  WARNING: _tabs/ exists but contains NO markdown files"
    WARNINGS=$((WARNINGS+1))
  else
    echo "✅ _tabs contains $TAB_COUNT navigation files"
  fi
fi

echo ""
echo "═════════════════════════════════════════"
if [ $ERRORS -gt 0 ]; then
  echo "❌ CRITICAL ERRORS: $ERRORS"
  echo "User content is MISSING or INCOMPLETE!"
  echo "DO NOT PROCEED with any git operations."
  exit 1
fi

if [ $WARNINGS -gt 0 ]; then
  echo "⚠️  WARNINGS: $WARNINGS (non-critical)"
fi

echo "✅ ALL CRITICAL CHECKS PASSED"
echo "Safe to proceed with git operations."
exit 0
