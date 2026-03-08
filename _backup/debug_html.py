"""Debug script to inspect site HTML structure."""
import requests
from bs4 import BeautifulSoup

def inspect_site(url, name):
    """Inspect HTML structure of a site."""
    print(f"\n{'='*70}")
    print(f"Inspecting: {name}")
    print(f"URL: {url}")
    print('='*70)
    
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Try different selectors
        selectors = [
            'article',
            '.post',
            '.entry',
            '.blog-post',
            '.item',
            '.news',
            'li',
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                print(f"\n[OK] Found {len(elements)} elements with selector: '{selector}'")
                
                # Show first element structure
                if len(elements) > 0:
                    first = elements[0]
                    print(f"  First element classes: {first.get('class')}")
                    print(f"  Contains <a> tags: {len(first.select('a'))}")
                    links = first.select('a')
                    if links:
                        print(f"  First link text: {links[0].get_text(strip=True)[:60]}")
                        print(f"  First link href: {links[0].get('href')}")
                        
    except Exception as e:
        print(f"❌ Error: {e}")

# Inspect problematic sites
inspect_site('https://msrc.microsoft.com/blog', 'Microsoft MSRC')
inspect_site('https://packetstorm.news/news/main/', 'Packet Storm Security')
