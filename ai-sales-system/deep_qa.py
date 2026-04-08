"""
===============================================================
  END-TO-END QA TEST — AI Sales OS
  Scrape → Research → Draft Verification
===============================================================
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from database import init_db, get_leads, get_lead
from agents.scraper_agent import run_scraper
from agents.research_agent import research_lead
from agents.email_agent import write_cold_email
from agents.whatsapp_agent import write_whatsapp_message

def run_deep_qa():
    print("\n--- 🔍 STEP 1: Real-World Scraping ---")
    # Finding a few real leads for verification
    leads = run_scraper(mode="automation", industry="clinics", city="Karachi", max_leads=3)
    print(f"✅ Found {len(leads)} leads.")
    
    # Get any lead from DB to ensure test proceeds
    db_leads = get_leads(limit=1)
    if not db_leads:
        print("❌ No leads found in database.")
        return
    
    lead = db_leads[0]
    lead_id = lead["id"]
    print(f"\n--- 🧠 STEP 2: Deep AI Research (Audit) ---")
    print(f"Analyzing: {lead['company']} ({lead.get('website','')})")
    
    research_result = research_lead(lead_id)
    # Reload lead to get saved research
    lead = get_lead(lead_id)
    research_data = json.loads(lead["research"]) if lead.get("research") else {}
    
    print("\n[AI AUDIT RESULTS]:")
    print(f"Fit Score: {lead.get('fit_score')}/10")
    print(f"Automation Gaps: {research_data.get('automation_audit', 'No audit generated')[:300]}...")
    
    print("\n--- ✉️ STEP 3: Message Drafting ---")
    # Test Email Draft
    subject, body = write_cold_email(lead, research_data)
    print("\n[PERSONALIZED EMAIL DRAFT]:")
    print(f"Subject: {subject}")
    print(f"Body:\n{body[:500]}...")
    
    # Test WA Draft
    wa_msg = write_whatsapp_message(lead, research_data)
    print("\n[PERSONALIZED WHATSAPP DRAFT]:")
    print(wa_msg)

if __name__ == "__main__":
    init_db()
    run_deep_qa()
