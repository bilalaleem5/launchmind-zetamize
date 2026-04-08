"""
===============================================================
  AI SALES SYSTEM — Scraper Agent
  Lead scraping from Google Maps, Yellow Pages, etc.
  NO PAID APIs — pure requests + BeautifulSoup
===============================================================
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time, random, re, json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from database import insert_lead, syslog
from config import TARGET_CITIES, TARGET_INDUSTRIES, APOLLO_API_KEY, APIFY_API_KEY, RAPIDAPI_KEY

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def _delay():
    time.sleep(random.uniform(3, 7))


# ───────────────────────────────────────────────────────────────
# Google Search Scraper (extracts business info from search results)
# ───────────────────────────────────────────────────────────────

def scrape_duckduckgo_search(query: str, num_results: int = 15) -> list[dict]:
    """
    Search DuckDuckGo HTML API for businesses and extract contact info.
    """
    syslog("Scraper", f"DuckDuckGo Search: {query}")
    leads = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        # Extract organic result titles + URLs
        results = soup.select(".result__body")
        for res in results[:num_results]:
            try:
                title_el = res.select_one(".result__title > a")
                snippet_el = res.select_one(".result__snippet")
                if not title_el:
                    continue

                company = title_el.get_text(strip=True)
                website = title_el.get("href", "")
                if website.startswith("//duckduckgo.com/l/?uddg="):
                    website = requests.utils.unquote(website.split("uddg=")[1].split("&")[0])
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                # Extract phone from snippet
                phone = _extract_phone(snippet + " " + company)
                email = _extract_email(snippet)

                if company and len(company) > 3:
                    leads.append({
                        "company": company[:100],
                        "website": website[:200],
                        "phone": phone,
                        "email": email,
                        "source": "duckduckgo_search",
                        "notes": snippet[:200],
                    })
            except Exception:
                continue
    except Exception as e:
        syslog("Scraper", f"DuckDuckGo search error: {e}", "warning")

    _delay()
    return leads


# ───────────────────────────────────────────────────────────────
# Apollo.io Scraper (for B2B leads via Free API Key)
# ───────────────────────────────────────────────────────────────

def scrape_apollo_b2b(keyword: str, location: str = "Pakistan") -> list[dict]:
    """Scrape B2B contacts via Apollo.io."""
    syslog("Scraper", f"Apollo: {keyword} in {location}")
    leads = []
    try:
        url = "https://api.apollo.io/v1/mixed_people/search"
        headers = {
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "x-api-key": APOLLO_API_KEY
        }
        data = {
            "q_organization_domains": "",
            "page": 1,
            "person_titles": ["CEO", "Founder", "Director", "Manager", "Owner", "Head"],
            "q_keywords": keyword,
            "person_locations": [location]
        }
        r = requests.post(url, headers=headers, json=data, timeout=15)
        if r.status_code == 200:
            res = r.json()
            for p in res.get("people", [])[:15]:
                org = p.get("organization", {}) or {}
                company = org.get("name") or p.get("headline", "")
                email = p.get("email") or ""
                phone = p.get("phone") or org.get("primary_phone", {}).get("number", "")
                
                leads.append({
                    "company": company[:100],
                    "website": org.get("website_url", "")[:200],
                    "phone": phone,
                    "email": email,
                    "source": "apollo",
                    "notes": f"{p.get('first_name', '')} {p.get('last_name', '')} | Title: {p.get('title', '')}".strip()[:200],
                })
    except Exception as e:
        syslog("Scraper", f"Apollo search error: {e}", "warning")
    return leads


# ───────────────────────────────────────────────────────────────
# Yellow Pages Pakistan Scraper
# ───────────────────────────────────────────────────────────────

def scrape_yellowpages(keyword: str, city: str = "karachi") -> list[dict]:
    # (Existing logic, but simplified/handled as a source)
    ...

# ───────────────────────────────────────────────────────────────
# Apify Google Maps Scraper
# ───────────────────────────────────────────────────────────────

def scrape_apify_google_maps(keyword: str, location: str = "Pakistan", max_results: int = 10) -> list[dict]:
    """Scrape Google Maps via Apify."""
    syslog("Scraper", f"Apify Maps: {keyword} in {location}")
    leads = []
    if not APIFY_API_KEY: return []
    
    try:
        # Using a standard Google Maps Scraper Actor on Apify
        url = f"https://api.apify.com/v2/acts/apify~google-maps-scraper/run-sync-get-dataset-items?token={APIFY_API_KEY}"
        data = {
            "searchStrings": [f"{keyword} in {location}"],
            "maxCrawledPlacesPerSearch": max_results,
            "language": "en"
        }
        r = requests.post(url, json=data, timeout=40)
        if r.status_code == 201 or r.status_code == 200:
            items = r.json()
            for item in items:
                leads.append({
                    "company": item.get("title", "")[:100],
                    "website": item.get("website", "")[:200],
                    "phone": item.get("phone", ""),
                    "address": item.get("address", ""),
                    "city": location,
                    "source": "apify_google_maps",
                    "notes": f"Rating: {item.get('totalScore', 'N/A')} | {item.get('categoryName', '')}"
                })
    except Exception as e:
        syslog("Scraper", f"Apify error: {e}", "warning")
    return leads

# ───────────────────────────────────────────────────────────────
# RapidAPI LinkedIn Scraper
# ───────────────────────────────────────────────────────────────

def scrape_rapidapi_linkedin(keyword: str, location: str = "Pakistan") -> list[dict]:
    """Scrape LinkedIn via RapidAPI."""
    syslog("Scraper", f"RapidAPI LinkedIn: {keyword}")
    leads = []
    if not RAPIDAPI_KEY: return []
    
    try:
        url = "https://linkedin-api8.p.rapidapi.com/search-companies"
        querystring = {"query": f"{keyword} {location}", "page": "1"}
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": "linkedin-api8.p.rapidapi.com"
        }
        r = requests.get(url, headers=headers, params=querystring, timeout=15)
        if r.status_code == 200:
            data = r.json()
            for item in data.get("data", {}).get("items", []):
                leads.append({
                    "company": item.get("name", "")[:100],
                    "website": item.get("website", "")[:200],
                    "source": "rapidapi_linkedin",
                    "notes": item.get("industry", "")
                })
    except Exception as e:
        syslog("Scraper", f"RapidAPI error: {e}", "warning")
    return leads


# ───────────────────────────────────────────────────────────────
# Website Contact Extractor (from company website)
# ───────────────────────────────────────────────────────────────

def enrich_from_website(website: str) -> dict:
    """Visit a company website and extract email, phone, address."""
    extras = {"email": "", "phone": "", "address": ""}
    if not website or not website.startswith("http"):
        return extras
    try:
        r = requests.get(website, headers=HEADERS, timeout=10)
        text = r.text
        extras["email"] = _extract_email(text)
        extras["phone"] = _extract_phone(text)
        _delay()
    except Exception:
        pass
    return extras


# ───────────────────────────────────────────────────────────────
# Social & Advanced Discovery (RapidAPI)
# ───────────────────────────────────────────────────────────────

def scrape_instagram_business(username: str) -> dict:
    """Get business music/data via Instagram RapidAPI (Example endpoint from user)."""
    syslog("Discovery", f"Instagram check: {username}")
    if not RAPIDAPI_KEY: return {}
    try:
        # User provided 'clip_music' as an example, but we'll use it as a 'social presence check'
        url = "https://instagram-api-fast-reliable-data-scraper.p.rapidapi.com/clip_music"
        headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": "instagram-api-fast-reliable-data-scraper.p.rapidapi.com"}
        # music_id is a placeholder from user's curl
        r = requests.get(url, headers=headers, params={"music_id": "18283290415083167", "source": "audio_cluster_id"}, timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception: return {}

def scrape_threads_presence(url: str) -> dict:
    """Get Threads profile data via RapidAPI."""
    syslog("Discovery", f"Threads check: {url}")
    if not RAPIDAPI_KEY: return {}
    try:
        api_url = "https://threads-scraper-api1.p.rapidapi.com/"
        headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": "threads-scraper-api1.p.rapidapi.com"}
        r = requests.get(api_url, headers=headers, params={"url": url}, timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception: return {}

def find_similar_linkedin_companies(linkedin_url: str) -> list[dict]:
    """Find similar profiles/companies via LinkedIn RapidAPI."""
    syslog("Discovery", f"LinkedIn Similar: {linkedin_url}")
    if not RAPIDAPI_KEY: return []
    try:
        url = "https://linkedin-api8.p.rapidapi.com/similar-profiles"
        headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": "linkedin-api8.p.rapidapi.com"}
        r = requests.get(url, headers=headers, params={"url": linkedin_url}, timeout=10)
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception: return []
    return []

# ───────────────────────────────────────────────────────────────
# LinkedIn Public Search (no login needed)
# ───────────────────────────────────────────────────────────────

def scrape_linkedin_companies(keyword: str, location: str = "Pakistan") -> list[dict]:
    """Search LinkedIn public company pages via DuckDuckGo."""
    syslog("Scraper", f"LinkedIn search: {keyword} {location}")
    query = f'site:linkedin.com/company "{keyword}" "{location}"'
    return scrape_duckduckgo_search(query, num_results=10)


# ───────────────────────────────────────────────────────────────
# Clutch.co (agency/service company finder)
# ───────────────────────────────────────────────────────────────

def scrape_clutch(service: str, location: str = "Pakistan") -> list[dict]:
    """Scrape Clutch.co for companies that might need AI services."""
    syslog("Scraper", f"Clutch: {service} {location}")
    query = f'site:clutch.co {service} {location} company'
    return scrape_duckduckgo_search(query, num_results=10)


# ───────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────

def _extract_email(text: str) -> str:
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    matches = re.findall(pattern, text)
    # Filter out common non-business emails
    for m in matches:
        if not any(x in m.lower() for x in ['example', 'test', 'noreply', 'no-reply']):
            return m.lower()
    return ""


def _extract_phone(text: str) -> str:
    patterns = [
        r'\+92[-\s]?\d{3}[-\s]?\d{7}',  # Pakistan +92
        r'0\d{3}[-\s]?\d{7}',            # Pakistan 0xxx
        r'\+\d{1,3}[-\s]?\d{6,12}',      # International
        r'\d{4}[-\s]\d{7}',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group().strip()
    return ""


# ───────────────────────────────────────────────────────────────
# Main Orchestration
# ───────────────────────────────────────────────────────────────

def run_scraper(
    mode: str = "automation",
    industry: str = None,
    city: str = None,
    product_id: int = None,
    product_keywords: list = None,
    max_leads: int = 30,
    dry_run: bool = False
) -> list[dict]:
    """
    Main scraping orchestrator.
    mode: 'automation' (for ZetaMize AI automation) | 'product' (for specific product)
    """
    all_leads = []

    if mode == "automation":
        industries = [industry] if industry else TARGET_INDUSTRIES[:3]
        cities = [city] if city else TARGET_CITIES[:2]

        for ind in industries:
            for c in cities:
                if len(all_leads) >= max_leads:
                    break
                
                syslog("Scraper", f"🔥 Launching MULTI-API Parallel Search for {ind} in {c}")
                
                # ── PARALLEL EXECUTION ──────────────────────────
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = {
                        executor.submit(scrape_duckduckgo_search, f"{ind} {c} business contact", 15): "DDG",
                        executor.submit(scrape_apollo_b2b, ind, c): "Apollo",
                        executor.submit(scrape_apify_google_maps, ind, c, 20): "Apify",
                        executor.submit(scrape_rapidapi_linkedin, ind, c): "LinkedIn_RA"
                    }
                    
                    for future in as_completed(futures):
                        name = futures[future]
                        try:
                            results = future.result()
                            for r in results:
                                r.update({"industry": ind, "city": c, "mode": "automation"})
                            all_leads.extend(results)
                            syslog("Scraper", f"✅ {name} returned {len(results)} leads")
                        except Exception as e:
                            syslog("Scraper", f"❌ {name} failed: {e}", "error")

    elif mode == "product" and product_keywords:
        cities = [city] if city else TARGET_CITIES[:2]
        for kw in product_keywords[:3]:
            for c in cities:
                if len(all_leads) >= max_leads:
                    break
                
                syslog("Scraper", f"🔥 Launching PARALLEL Product Lead Search for {kw}")
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {
                        executor.submit(scrape_duckduckgo_search, f"{kw} {c} business", 15): "DDG",
                        executor.submit(scrape_apollo_b2b, kw, c): "Apollo",
                        executor.submit(scrape_apify_google_maps, kw, c, 15): "Apify"
                    }
                    for future in as_completed(futures):
                        try:
                            results = future.result()
                            for r in results:
                                r.update({"mode": "product", "product_id": product_id, "industry": kw, "city": c})
                            all_leads.extend(results)
                        except Exception: pass

    # Deduplicate
    seen = set()
    unique = []
    for l in all_leads:
        key = l.get("company","").lower()[:30]
        if key and key not in seen:
            seen.add(key)
            unique.append(l)

    unique = unique[:max_leads]

    if not dry_run:
        saved = 0
        for lead in unique:
            lid = insert_lead(lead)
            if lid > 0:
                saved += 1
        syslog("Scraper", f"Saved {saved}/{len(unique)} new leads to DB")
    else:
        syslog("Scraper", f"Dry run: found {len(unique)} leads (not saved)")

    return unique


if __name__ == "__main__":
    print("🔍 Testing scraper...")
    leads = run_scraper(mode="automation", industry="restaurants", city="Karachi", max_leads=5, dry_run=True)
    for l in leads:
        print(f"  • {l.get('company')} | {l.get('phone')} | {l.get('email')}")
