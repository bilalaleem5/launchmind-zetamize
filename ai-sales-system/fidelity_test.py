"""
===============================================================
  ADVANCED DISCOVERY FIDELITY TEST — AI Sales OS
  Manual Lead → Social Discovery → AI Audit → Draft
===============================================================
"""

import sys, os
import json
import io

# Set UTF-8 for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── MOCK AI ROUTER FOR ADVANCED TEST ─────────────────────────
import agents.ai_router
def mock_ai_call(prompt, system="", temperature=0.7, prefer=None):
    if "email" in prompt.lower():
        return "SUBJECT: Elevating ZetaFin's Brand Voice with AI\nBODY:\nHi,\n\nI was just looking at your Instagram and noticed your energetic, youth-focused brand tone. \n\nHowever, your website's transaction processing seems manual, which contradicts that high-tech vibe. Automating this could save ~$2,500/mo and keep your operations as fast as your brand.\n\nSetup takes 48 hours. Ready to sync?\n\nBest,\nBilal"
    if "whatsapp" in prompt.lower():
        return "Hi! Love the energy on your IG. Noticed a manual gap in your transaction flow though. We can automate that to save $2k/mo. Matching your fast brand vibe! 🚀"
    return "{}"

agents.ai_router.ai_call = mock_ai_call
# ───────────────────────────────────────────────────────────────

from database import init_db, get_lead, insert_lead, get_conn
from agents.research_agent import research_lead
from agents.email_agent import write_cold_email
from agents.whatsapp_agent import write_whatsapp_message

def run_advanced_test():
    print("\n--- 📍 STEP 1: Targeted Lead Injection ---")
    company = "ZetaFin" 
    website = "https://zetafin.app" 
    
    data = {
        "company": company,
        "website": website,
        "industry": "FinTech",
        "phone": "923001234567",
        "email": "test@zetafin.app"
    }
    lead_id = insert_lead(data)
    if lead_id == -1:
        conn = get_conn()
        lead_id = conn.execute("SELECT id FROM leads WHERE company=?", (company,)).fetchone()[0]
        conn.close()
    
    print(f"✅ Target Lead ID: {lead_id}")
    
    print(f"\n--- 🧠 STEP 2: Advanced Social Discovery & Research ---")
    # Simulating what the research_lead would find now with Phase 8
    research_data = {
        "industry": "FinTech / SaaS",
        "social_tone": "Energetic and youth-focused (Verified via Instagram)",
        "automation_audit": "Manual processing for international transactions identified.",
        "roi_proof_numbers": "Automating this could save ~$2,500/mo in overhead.",
        "implementation_ease": "Setup in 48 hours with zero downtime.",
        "fit_score": 9,
        "personalization_hooks": ["Energetic social presence", "Oracle Cloud efficiency"],
        "recommended_service": "AI Transaction Automation",
        "outreach_tone": "semi-formal",
        "fit_reason": "High-fit B2B with social-to-ops gap."
    }
    
    print("\n[AI STRATEGIC AUDIT (Phase 8)]:")
    print(json.dumps(research_data, indent=2))
    
    print(f"\n--- ✉️ STEP 3: Hyper-Personalized Drafting ---")
    
    # Email
    subject, body = write_cold_email(get_lead(lead_id), research_data)
    print("\n[DRAFT EMAIL]:")
    print(f"Subject: {subject}")
    print("-" * 30)
    print(body)
    print("-" * 30)
    
    # WhatsApp
    wa_msg = write_whatsapp_message(get_lead(lead_id), research_data)
    print("\n[DRAFT WHATSAPP]:")
    print("-" * 30)
    print(wa_msg)
    print("-" * 30)

if __name__ == "__main__":
    init_db()
    run_advanced_test()
