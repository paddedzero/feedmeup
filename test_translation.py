#!/usr/bin/env python3
"""Test script to check if translation is working"""
import yaml

with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

print("=== Checking for Japanese/Asian feeds ===\n")
for source in config['sources']:
    name = source.get('name', '')
    url = source.get('url', '')
    if any(word in name.lower() for word in ['japan', 'japanese', 'asia', 'hong kong', 'singapore', 'korea', 'china']):
        print(f"{name}")
        print(f"  URL: {url}")
        print(f"  Category: {source.get('category', 'N/A')}")
        print()

print("\n=== Translation Config ===")
print(f"Translation enabled: {config.get('translation', {}).get('enabled', False)}")
print(f"Gemini summarization enabled: {config.get('synthesis', {}).get('enable_gemini_summarization', False)}")
