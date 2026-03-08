"""Test Packet Storm extraction."""
import requests
from bs4 import BeautifulSoup

r = requests.get('https://packetstorm.news/news/main/', headers={'User-Agent': 'Mozilla/5.0'})
soup = BeautifulSoup(r.content, 'html.parser')

# Find news items
items = soup.select('dl.news dt')
print(f"Found {len(items)} news items using 'dl.news dt' selector")

for i, item in enumerate(items[:3]):
    link = item.select_one('a')
    if link:
        print(f"\nItem {i+1}:")
        print(f"  Title: {link.get_text(strip=True)}")
        print(f"  Link: {link.get('href')}")
