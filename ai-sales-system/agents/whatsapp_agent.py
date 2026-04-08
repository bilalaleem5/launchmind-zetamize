"""
===============================================================
  AI SALES SYSTEM — WhatsApp Agent
  Validates numbers + sends messages via WhatsApp Web (Selenium)
===============================================================
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time, json, re
import requests
from agents.ai_router import ai_call
from database import get_lead, update_lead, log_outreach, schedule_followup, update_deal_stage, syslog
from config import (BUSINESS_NAME, GMAIL_SENDER_NAME, WEBSITE,
                    FOLLOW_UP_DAYS, WHATSAPP_DELAY_SECONDS, BASE_DIR)
from datetime import datetime, timedelta

# WhatsApp session dir — saves login so you don't scan QR every time
WA_SESSION_DIR = os.path.join(BASE_DIR, "data", "wa_session")

# ───────────────────────────────────────────────────────────────
# Number Validation
# ───────────────────────────────────────────────────────────────

def format_number(phone: str) -> str:
    """Clean and format phone number to international format."""
    digits = re.sub(r'\D', '', phone)
    if digits.startswith("0") and len(digits) >= 10:
        digits = "92" + digits[1:]  # Pakistan local → international
    if not digits.startswith("+"):
        digits = "+" + digits
    return digits


def is_valid_whatsapp(phone: str) -> bool:
    """
    Check if number is on WhatsApp using wa.me redirect check.
    Returns True if WhatsApp profile exists.
    """
    try:
        formatted = format_number(phone).replace("+", "")
        url = f"https://wa.me/{formatted}"
        r = requests.get(url, timeout=10, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        # If it redirects to WhatsApp app page, number is valid
        return "whatsapp" in r.url.lower() or "send" in r.text.lower()
    except Exception:
        return False


# ───────────────────────────────────────────────────────────────
# Message Writer
# ───────────────────────────────────────────────────────────────

def write_whatsapp_message(lead: dict, research: dict, product_info: dict = None,
                           is_followup: bool = False, attempt: int = 1) -> str:
    """Generate a conversational WhatsApp message using AI."""
    company = lead.get("company", "")
    contact_name = lead.get("name", "")
    industry = lead.get("industry", "")
    pain_points = research.get("pain_points", ["manual processes"])
    hooks = research.get("personalization_hooks", [])

    pain = pain_points[0] if pain_points else "manual processes"
    hook = hooks[0] if hooks else f"your {industry} business"
    salutation = f"Hi {contact_name} 👋" if contact_name else "Hi there 👋"

    if is_followup:
        prompt = f"""
Write a short WhatsApp follow-up message (attempt #{attempt}) from {GMAIL_SENDER_NAME} of {BUSINESS_NAME}.

Target: {company} ({industry})
Pain point: {pain}

Rules:
- MAX 3 sentences
- Super casual WhatsApp tone
- Different angle: curiosity or social proof
- End with a simple question
- No long paragraphs, no formal sign-off
- Emojis: 1-2 max
"""
    elif product_info:
        features = product_info.get("features", [])
        benefit = research.get("key_benefit_for_them", "")
        prompt = f"""
Write a short WhatsApp cold outreach message for {company} about our product.

Product: {product_info.get('name', '')}
Their main benefit: {benefit}
Pain point: {pain}

Rules:
- Start with: {salutation}
- 3-4 short sentences
- Conversational, not salesy
- Mention the product helps specifically with their {industry} pain point
- End with a soft question (not "buy now")
- 1-2 emojis max
- NO long blocks of text
"""
    else:
        audit_hook = research.get("automation_audit", "")
        roi_proof = research.get("roi_proof_numbers", "")
        ease_hook = research.get("implementation_ease", "")
        social_tone = research.get("social_tone", "")
        
        prompt = f"""
Write a short, high-impact WhatsApp message for {company}.

KEY INFO:
- Start with: {salutation}
- Lead with Audit Hook (e.g. 'I was just looking at your site and noticed...')
- ROI Mention: {roi_proof}
- Ease of Use: {ease_hook}
- Social Vibe: {social_tone} (Match this!)
- Goal: Get them curious about AI automation.

RULES:
1. MAX 4 short sentences.
2. NO SALESY CLICHES.
3. Super conversational.
4. End with a soft curiosity question (e.g. "Worth exploring for your team?").
5. 1-2 emojis max.
"""

    try:
        msg = ai_call(prompt, temperature=0.85)
        # Clean up
        msg = msg.strip().strip('"').strip("'")
        return msg
    except Exception as e:
        syslog("WhatsApp", f"AI message failed: {e}", "warning")
        return (f"{salutation}\n\nI noticed {company} might benefit from AI automation "
                f"— specifically around {pain}. We help {industry} businesses save 10+ "
                f"hours/week. Would a quick chat be useful? 🙂")


# ───────────────────────────────────────────────────────────────
# Selenium WhatsApp Sender
# ───────────────────────────────────────────────────────────────

def _get_driver():
    """Initialize Chrome WebDriver with persistent session."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        options = Options()
        options.add_argument(f"--user-data-dir={WA_SESSION_DIR}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        driver = webdriver.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        syslog("WhatsApp", f"Could not start Chrome: {e}", "error")
        return None


def send_whatsapp_message(phone: str, message: str) -> bool:
    """
    Send a WhatsApp message via WhatsApp Web automation.
    First run: QR code scan needed. After that, session is saved.
    """
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.keys import Keys

        formatted = format_number(phone).replace("+", "")
        url = f"https://web.whatsapp.com/send?phone={formatted}&text={requests.utils.quote(message)}"

        driver = _get_driver()
        if not driver:
            return False

        try:
            driver.get(url)
            wait = WebDriverWait(driver, 60)  # 60s for QR scan on first run

            # Wait for chat to load (message input box)
            input_box = wait.until(EC.presence_of_element_located(
                (By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]')
            ))

            time.sleep(2)
            input_box.send_keys(Keys.ENTER)  # Send the pre-filled message
            time.sleep(WHATSAPP_DELAY_SECONDS)
            syslog("WhatsApp", f"✅ Message sent to {phone}")
            return True

        finally:
            driver.quit()

    except Exception as e:
        syslog("WhatsApp", f"❌ Failed to send to {phone}: {e}", "error")
        return False


# ───────────────────────────────────────────────────────────────
# Main WhatsApp Outreach
# ───────────────────────────────────────────────────────────────

def send_whatsapp_outreach(lead_id: int, product_info: dict = None,
                           is_followup: bool = False, attempt: int = 1) -> bool:
    """Full pipeline: validate number → write message → send → log."""
    lead = get_lead(lead_id)
    if not lead:
        return False

    phone = lead.get("phone", "")
    if not phone:
        syslog("WhatsApp", f"No phone for lead {lead_id} ({lead.get('company')})", "warning")
        return False

    # Check if number is on WhatsApp
    syslog("WhatsApp", f"Checking WA for {lead.get('company')}: {phone}")
    wa_valid = is_valid_whatsapp(phone)
    update_lead(lead_id, wa_valid=1 if wa_valid else 0)

    if not wa_valid:
        syslog("WhatsApp", f"Number {phone} not on WhatsApp", "warning")
        return False

    # Load research
    research = {}
    if lead.get("research"):
        try:
            research = json.loads(lead["research"])
        except Exception:
            pass

    # Write message
    message = write_whatsapp_message(lead, research, product_info, is_followup, attempt)

    # Send
    success = send_whatsapp_message(phone, message)

    # Log
    status = "sent" if success else "failed"
    log_outreach(lead_id, "whatsapp", message, status=status)

    if success:
        if not lead.get("status") == "replied":
            update_lead(lead_id, status="contacted")
        update_deal_stage(lead_id, "contacted")

        # Schedule WA follow-up
        if not is_followup and attempt < 3:
            followup_date = (datetime.now() + timedelta(days=FOLLOW_UP_DAYS)).isoformat()
            schedule_followup(lead_id, "whatsapp", followup_date, attempt + 1)

    return success


if __name__ == "__main__":
    print("📱 WhatsApp Agent ready.")
    print("\nNote: First run will open Chrome and ask you to scan QR code.")
    print("After that, session is saved. No QR needed again.\n")
    test_phone = input("Enter a test phone number (with country code): ").strip()
    if test_phone:
        valid = is_valid_whatsapp(test_phone)
        print(f"WhatsApp valid: {valid}")
