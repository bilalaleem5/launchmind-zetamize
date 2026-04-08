import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}

url = "https://html.duckduckgo.com/html/?q=dental+clinics+business+Karachi+contact+phone"
r = requests.get(url, headers=HEADERS)
print(f"Status: {r.status_code}")

soup = BeautifulSoup(r.text, "html.parser")
results = soup.select(".result__body")
print(f"Found {len(results)} results")
for res in results[:3]:
    title_el = res.select_one(".result__title > a")
    snippet_el = res.select_one(".result__snippet")
    print(title_el.get_text(strip=True) if title_el else "No title")
    print(snippet_el.get_text(strip=True) if snippet_el else "No snippet")
    print("---")
