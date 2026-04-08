"""
===============================================================
  AI SALES SYSTEM — Main CLI Orchestrator
  The central command center to run all agents
  Usage: python run.py
===============================================================
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from database import (init_db, get_leads, get_products, insert_product,
                      get_pipeline_stats, update_deal_stage, syslog, get_lead)
from config import MIN_FIT_SCORE

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║          🤖  AI SALES SYSTEM — ZetaMize SDR Bot              ║
║          Autonomous Lead Gen → Outreach → Pipeline           ║
╚══════════════════════════════════════════════════════════════╝
"""


def print_banner():
    print(BANNER)


def print_menu():
    print("\n" + "─"*60)
    print("  MAIN MENU")
    print("─"*60)
    print("  [1]  🔍  Scrape New Leads")
    print("  [2]  🧠  Research Leads (AI Analysis)")
    print("  [3]  📧  Send Emails to Qualified Leads")
    print("  [4]  📱  Send WhatsApp Messages")
    print("  [5]  📧📱 Full Outreach (Email + WhatsApp)")
    print("  [6]  🔄  Run Follow-ups (Due Today)")
    print("  [7]  📊  View Pipeline Stats")
    print("  [8]  📋  List Leads")
    print("  [9]  🏷️  Manage Products (Product Mode)")
    print("  [10] 🎯  Full Auto-Run (Scrape→Research→Outreach)")
    print("  [11] 🌐  Launch Dashboard (localhost:5000)")
    print("  [12] ✅  Mark Lead Status")
    print("  [0]  ❌  Exit")
    print("─"*60)


def choose_mode() -> tuple:
    """Let user choose between automation or product mode."""
    print("\n  MODE:")
    print("  [1] AI Automation (ZetaMize services)")
    print("  [2] Product-specific leads")
    choice = input("  Choose mode (1/2): ").strip()

    if choice == "2":
        products = get_products()
        if not products:
            print("  ⚠️  No products saved. Let's add one first.")
            return "product", None, add_product()
        print("\n  Your products:")
        for i, p in enumerate(products):
            print(f"  [{i+1}] {p['name']}")
        print(f"  [{len(products)+1}] Add new product")
        sel = int(input("  Select: ").strip()) - 1
        if sel == len(products):
            product = add_product()
        else:
            product = products[sel]
        return "product", None, product
    else:
        return "automation", None, None


def add_product() -> dict:
    """Interactive product setup."""
    print("\n  📦 Add New Product")
    name = input("  Product name: ").strip()
    description = input("  Description: ").strip()
    features_raw = input("  Features (comma-separated): ").strip()
    features = [f.strip() for f in features_raw.split(",") if f.strip()]
    target = input("  Target audience: ").strip()
    price = input("  Price range (e.g. $50-$200/mo): ").strip()

    data = {
        "name": name,
        "description": description,
        "features": features,
        "target_audience": target,
        "price_range": price,
    }
    pid = insert_product(data)
    data["id"] = pid
    print(f"  ✅ Product '{name}' saved (ID: {pid})")
    return data


def run_scrape_menu():
    mode, _, product = choose_mode()
    industry = input("  Industry/keyword (or Enter for defaults): ").strip() or None
    city = input("  City (or Enter for defaults): ").strip() or None
    max_l = int(input("  Max leads to scrape [20]: ").strip() or "20")

    from agents.scraper_agent import run_scraper
    keywords = None
    product_id = None
    if product:
        import json as js
        feats = product.get("features", [])
        if isinstance(feats, str):
            feats = js.loads(feats)
        keywords = [product["name"]] + feats[:2]
        product_id = product.get("id")

    print(f"\n  🔍 Scraping leads...")
    leads = run_scraper(
        mode=mode, industry=industry, city=city,
        product_id=product_id, product_keywords=keywords,
        max_leads=max_l
    )
    print(f"\n  ✅ Found {len(leads)} leads (saved to database)")


def run_research_menu():
    mode, _, product = choose_mode()
    leads = get_leads(status="new", mode=mode, limit=50)
    print(f"\n  Found {len(leads)} unresearched leads")
    if not leads:
        print("  Scrape some leads first!")
        return

    limit = int(input(f"  Research how many? [{min(10,len(leads))}]: ").strip() or str(min(10,len(leads))))
    leads = leads[:limit]

    product_info = None
    if product:
        import json as js
        feats = product.get("features","[]")
        if isinstance(feats, str):
            feats = js.loads(feats)
        product_info = {**product, "features": feats}

    from agents.research_agent import research_lead
    for lead in leads:
        result = research_lead(lead["id"], product_info)
        score = result.get("fit_score", 0)
        status = "✅" if score >= MIN_FIT_SCORE else "⚠️"
        print(f"  {status} {lead['company'][:40]} — fit: {score}/10")


def run_email_menu():
    mode, _, product = choose_mode()
    leads = get_leads(status="researched", mode=mode, limit=50)
    qualified = [l for l in leads if (l.get("fit_score") or 0) >= MIN_FIT_SCORE and l.get("email")]
    print(f"\n  {len(qualified)} qualified leads with emails")
    if not qualified:
        print("  Run research first, or lower MIN_FIT_SCORE in config.py")
        return

    limit = int(input(f"  Send to how many? [{min(5,len(qualified))}]: ").strip() or str(min(5,len(qualified))))
    qualified = qualified[:limit]

    product_info = None
    if product:
        import json as js
        feats = product.get("features","[]")
        if isinstance(feats, str):
            feats = js.loads(feats)
        product_info = {**product, "features": feats}

    from agents.email_agent import send_outreach_email
    sent = 0
    for lead in qualified:
        print(f"  📧 Sending to {lead['company']}...")
        ok = send_outreach_email(lead["id"], product_info)
        if ok:
            sent += 1
    print(f"\n  ✅ Sent {sent}/{len(qualified)} emails")


def run_whatsapp_menu():
    mode, _, product = choose_mode()
    leads = get_leads(status="researched", mode=mode, limit=50)
    qualified = [l for l in leads if (l.get("fit_score") or 0) >= MIN_FIT_SCORE and l.get("phone")]
    print(f"\n  {len(qualified)} qualified leads with phone numbers")
    if not qualified:
        print("  Run research first!")
        return

    limit = int(input(f"  Send to how many? [{min(3,len(qualified))}]: ").strip() or str(min(3,len(qualified))))
    qualified = qualified[:limit]

    product_info = None
    if product:
        import json as js
        feats = product.get("features","[]")
        if isinstance(feats, str):
            feats = js.loads(feats)
        product_info = {**product, "features": feats}

    print("  ⚠️  First run: Chrome will open, scan QR code, then session is saved.")
    input("  Press Enter to continue...")

    from agents.whatsapp_agent import send_whatsapp_outreach
    sent = 0
    for lead in qualified:
        print(f"  📱 Messaging {lead['company']}...")
        ok = send_whatsapp_outreach(lead["id"], product_info)
        if ok:
            sent += 1
    print(f"\n  ✅ Sent {sent}/{len(qualified)} WhatsApp messages")


def run_full_auto():
    """Full autonomous pipeline: scrape → research → email + WA."""
    print("\n  🤖 FULL AUTO-RUN MODE")
    mode, _, product = choose_mode()
    industry = input("  Industry/keyword: ").strip() or None
    city = input("  City: ").strip() or None

    product_info = None
    product_id = None
    keywords = None
    if product:
        import json as js
        feats = product.get("features","[]")
        if isinstance(feats, str):
            feats = js.loads(feats)
        product_info = {**product, "features": feats}
        product_id = product.get("id")
        keywords = [product["name"]] + feats[:2]

    print("\n  Step 1/3: Scraping leads...")
    from agents.scraper_agent import run_scraper
    leads = run_scraper(mode=mode, industry=industry, city=city,
                        product_id=product_id, product_keywords=keywords, max_leads=20)
    print(f"  → {len(leads)} leads found")

    print("\n  Step 2/3: Researching leads...")
    from agents.research_agent import research_lead
    db_leads = get_leads(status="new", mode=mode, limit=20)
    qualified_ids = []
    for l in db_leads:
        result = research_lead(l["id"], product_info)
        score = result.get("fit_score", 0)
        if score >= MIN_FIT_SCORE:
            qualified_ids.append(l["id"])
        print(f"  → {l['company'][:35]}: {score}/10 {'✅' if score >= MIN_FIT_SCORE else '❌'}")

    print(f"\n  {len(qualified_ids)} qualified leads")

    print("\n  Step 3/3: Sending outreach...")
    from agents.email_agent import send_outreach_email
    from agents.whatsapp_agent import send_whatsapp_outreach
    email_sent = wa_sent = 0
    for lid in qualified_ids:
        l = get_lead(lid)
        if l and l.get("email"):
            ok = send_outreach_email(lid, product_info)
            if ok:
                email_sent += 1
        if l and l.get("phone"):
            ok = send_whatsapp_outreach(lid, product_info)
            if ok:
                wa_sent += 1

    print(f"\n  ✅ Auto-run complete: {email_sent} emails + {wa_sent} WA messages sent")


def show_stats():
    stats = get_pipeline_stats()
    print("\n  ─────────── PIPELINE STATS ───────────")
    print(f"  Total Leads:     {stats['total_leads']}")
    print(f"  Emails Sent:     {stats['emails_sent']}")
    print(f"  WA Messages:     {stats['wa_sent']}")
    print(f"  ─────────────────────────────────────")
    print(f"  New:             {stats.get('new',0)}")
    print(f"  Contacted:       {stats.get('contacted',0)}")
    print(f"  Replied:         {stats.get('replied',0)}")
    print(f"  Meeting Booked:  {stats.get('meeting_booked',0)}")
    print(f"  Closed Won:      {stats.get('closed_won',0)} 🎉")
    print(f"  Closed Lost:     {stats.get('closed_lost',0)}")
    print(f"  Cold:            {stats.get('cold',0)}")
    print(f"  ─────────────────────────────────────")


def list_leads_menu():
    status_filter = input("  Filter by status (or Enter for all): ").strip() or None
    leads = get_leads(status=status_filter, limit=30)
    print(f"\n  {'ID':<5} {'Company':<30} {'Email':<25} {'Score':<6} {'Status':<15}")
    print("  " + "─"*80)
    for l in leads:
        print(f"  {l['id']:<5} {str(l.get('company',''))[:28]:<30} "
              f"{str(l.get('email',''))[:23]:<25} "
              f"{l.get('fit_score',0):<6} {l.get('status',''):<15}")


def mark_lead_menu():
    lid = int(input("  Lead ID: ").strip())
    print("  Status: [1] Replied  [2] Meeting Booked  [3] Won  [4] Lost")
    s = input("  Choose: ").strip()
    from agents.followup_agent import mark_lead_replied, mark_meeting_booked, mark_deal_closed
    if s == "1":
        mark_lead_replied(lid)
        print("  ✅ Marked as replied")
    elif s == "2":
        dt = input("  Meeting datetime (e.g. 2026-04-10 14:00): ").strip()
        mark_meeting_booked(lid, dt)
        print("  ✅ Meeting booked!")
    elif s == "3":
        mark_deal_closed(lid, won=True)
        print("  🎉 Deal marked as WON!")
    elif s == "4":
        mark_deal_closed(lid, won=False)
        print("  Deal marked as lost")


def launch_dashboard():
    import subprocess
    print("  🌐 Launching dashboard at http://localhost:5000 ...")
    subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), "dashboard", "app.py")])
    import webbrowser, time
    time.sleep(2)
    webbrowser.open("http://localhost:5000")
    print("  Dashboard launched! (Keep this window open)")


def main():
    print_banner()
    print("  Initializing database...")
    init_db()
    print("  ✅ Ready!\n")

    while True:
        print_menu()
        choice = input("  Your choice: ").strip()

        try:
            if choice == "0":
                print("  Goodbye! 👋")
                break
            elif choice == "1":
                run_scrape_menu()
            elif choice == "2":
                run_research_menu()
            elif choice == "3":
                run_email_menu()
            elif choice == "4":
                run_whatsapp_menu()
            elif choice == "5":
                run_email_menu()
                run_whatsapp_menu()
            elif choice == "6":
                from agents.followup_agent import run_followups
                stats = run_followups()
                print(f"  ✅ Follow-ups done: {stats}")
            elif choice == "7":
                show_stats()
            elif choice == "8":
                list_leads_menu()
            elif choice == "9":
                products = get_products()
                if products:
                    print(f"\n  Your products ({len(products)}):")
                    for p in products:
                        print(f"  • [{p['id']}] {p['name']}: {p.get('description','')[:60]}")
                add_new = input("  Add new product? (y/n): ").strip().lower()
                if add_new == "y":
                    add_product()
            elif choice == "10":
                run_full_auto()
            elif choice == "11":
                launch_dashboard()
            elif choice == "12":
                mark_lead_menu()
            else:
                print("  Invalid choice, try again.")
        except KeyboardInterrupt:
            print("\n  Cancelled.")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback; traceback.print_exc()

        input("\n  Press Enter to continue...")


# ── Test flags ──────────────────────────────────────────────────

if __name__ == "__main__":
    if "--test-email" in sys.argv:
        from config import GMAIL_ADDRESS
        from agents.email_agent import send_gmail
        ok = send_gmail(GMAIL_ADDRESS, "AI Sales System — Gmail Test", "Connection working! ✅")
        print("✅ Email test passed!" if ok else "❌ Email test failed!")
    elif "--test-gemini" in sys.argv:
        from agents.ai_router import ai_call
        r = ai_call("Say 'ZetaMize AI Sales System is live!'")
        print(f"✅ AI Response: {r}")
    elif "--test-db" in sys.argv:
        init_db()
        print("✅ Database test passed!")
    elif "--test-scraper" in sys.argv:
        from agents.scraper_agent import run_scraper
        leads = run_scraper(industry="clinics", city="Karachi", max_leads=5, dry_run=True)
        print(f"✅ Scraper test: found {len(leads)} leads")
    else:
        main()
