import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

url = "https://www.google.com/search?q=restaurants+business+Karachi+contact+phone"
r = requests.get(url, headers=HEADERS)
print(f"Status Code: {r.status_code}")
print("Response text snippet:", r.text[:500])

soup = BeautifulSoup(r.text, "html.parser")
results = soup.select("div.g")
print(f"Found {len(results)} div.g elements")
for res in results[:2]:
    title_el = res.select_one("h3")
    print("Title:", title_el.get_text(strip=True) if title_el else "None")
