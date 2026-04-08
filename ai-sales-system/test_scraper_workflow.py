from agents.scraper_agent import run_scraper

print("--- Testing Automation Mode (Local Businesses) ---")
l_local = run_scraper(mode="automation", industry="dental clinics", city="Islamabad", max_leads=3, dry_run=True)
for l in l_local:
    print(f"[{l.get('source')}] {l.get('company')} | P({l.get('phone')}) E({l.get('email')})")

print("\n--- Testing Automation Mode (B2B Businesses) ---")
l_b2b = run_scraper(mode="automation", industry="software agency", city="Lahore", max_leads=3, dry_run=True)
for l in l_b2b:
    print(f"[{l.get('source')}] {l.get('company')} | P({l.get('phone')}) E({l.get('email')}) Notes: {l.get('notes')}")
