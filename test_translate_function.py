#!/usr/bin/env python3
"""Test translation functionality"""
import sys
sys.path.insert(0, '.')

from fetch_news import translate_entry, init_gemini_client, GEMINI_CLIENT
import os

# Initialize Gemini (you'll need API key)
api_key = os.environ.get("GEMINI_API_KEY", "")
if api_key:
    init_gemini_client(api_key, "gemini-1.5-flash")
else:
    print("⚠️  No GEMINI_API_KEY found - translation will be skipped")

# Test entry with Japanese text
test_entry = {
    "title": "サイバーセキュリティ対策の強化について",
    "summary": "政府は新しいサイバーセキュリティ基本法を発表しました。この法律は、重要インフラの保護を強化します。",
    "description": "政府は新しいサイバーセキュリティ基本法を発表しました。この法律は、重要インフラの保護を強化します。",
    "link": "https://example.com"
}

print("=== Original Entry ===")
print(f"Title: {test_entry['title']}")
print(f"Summary: {test_entry['summary'][:100]}")

# Translate
config = {"translation": {"enabled": True}}
translated = translate_entry(test_entry.copy(), config)

print("\n=== After Translation ===")
print(f"Title: {translated['title']}")
print(f"Summary: {translated['summary'][:100]}")
print(f"Translated: {translated.get('_translated', False)}")
if translated.get('_original_title'):
    print(f"Original title preserved: {translated['_original_title'][:50]}")
