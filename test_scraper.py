"""
Test script for web scraper module.
Tests scraping functionality on priority sites.
"""

import requests
from scraper import scrape_site, SCRAPER_REGISTRY

# Test sites (from config.yaml Scraping Candidates)
TEST_SITES = [
    ('Microsoft MSRC', 'https://msrc.microsoft.com/blog'),
    ('Packet Storm Security', 'https://packetstorm.news/news/main/'),
    ('CISA', 'https://www.cisa.gov/news-events/cybersecurity-advisories'),
]

def test_scrapers():
    """Test each priority scraper."""
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; RSS-Bot/1.0)'})
    
    print("=" * 70)
    print("WEB SCRAPER TEST - Priority Sites")
    print("=" * 70)
    
    for site_name, url in TEST_SITES:
        print(f"\n[TEST] {site_name}")
        print(f"  URL: {url}")
        print(f"  Scraper: {SCRAPER_REGISTRY.get(site_name, 'GenericBlogScraper').__name__}")
        
        try:
            articles, status = scrape_site(session, site_name, url)
            
            if status == "OK" and articles:
                print(f"  ✅ SUCCESS: Extracted {len(articles)} articles")
                print(f"\n  Sample article:")
                sample = articles[0]
                print(f"    Title: {sample.get('title', 'N/A')[:80]}")
                print(f"    Link: {sample.get('link', 'N/A')}")
                print(f"    Summary: {sample.get('summary', 'N/A')[:100]}...")
            elif status == "NO_ARTICLES":
                print(f"  ⚠️  WARNING: Scraper succeeded but found 0 articles")
            else:
                print(f"  ❌ FAILED: {status}")
                
        except Exception as e:
            print(f"  ❌ EXCEPTION: {str(e)}")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    test_scrapers()
