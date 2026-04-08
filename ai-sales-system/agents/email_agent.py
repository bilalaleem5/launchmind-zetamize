"""
===============================================================
  AI SALES SYSTEM — Email Agent
  Writes personalized cold emails + sends via Gmail SMTP
===============================================================
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import smtplib, json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from agents.ai_router import ai_call
from database import get_lead, update_lead, log_outreach, schedule_followup, update_deal_stage, syslog
from config import (GMAIL_ADDRESS, GMAIL_APP_PASSWORD, GMAIL_SENDER_NAME,
                    BUSINESS_NAME, WEBSITE, CALENDLY_LINK, FOLLOW_UP_DAYS)
from datetime import datetime, timedelta

# ───────────────────────────────────────────────────────────────
# Email Writer
# ───────────────────────────────────────────────────────────────

def write_cold_email(lead: dict, research: dict, product_info: dict = None, is_followup: bool = False, attempt: int = 1) -> tuple[str, str]:
    """
    Generate a personalized cold email using AI.
    Returns (subject, body) tuple.
    """
    company = lead.get("company", "")
    contact_name = lead.get("name", "")
    salutation = f"Hi {contact_name}," if contact_name else "Hi there,"
    industry = lead.get("industry", "")
    pain_points = research.get("pain_points", ["manual processes"])
    hooks = research.get("personalization_hooks", [])
    tone = research.get("outreach_tone", "semi-formal")

    hook_str = hooks[0] if hooks else f"your {industry} business"
    pain_str = pain_points[0] if pain_points else "manual processes"

    if is_followup:
        prompt = f"""
Write a follow-up cold email (attempt #{attempt}) for {BUSINESS_NAME} to {company}.

Context:
- We already sent them a cold email {FOLLOW_UP_DAYS * attempt} days ago, no reply
- Their main pain point: {pain_str}
- Previous hook: {hook_str}
- Tone: {tone}

Rules:
- SHORT (max 120 words in body)
- Different angle from first email — add urgency or social proof
- Reference that we emailed before ("Following up on my previous note...")
- End with a clear, low-friction CTA (reply/15-min call)
- Subject line should be different from previous

Return format:
SUBJECT: [subject line here]
BODY:
[email body here]

Sign off as: {GMAIL_SENDER_NAME}
Website: {WEBSITE}
"""
    elif product_info:
        features = ", ".join(product_info.get("features", [])[:3])
        benefit = research.get("key_benefit_for_them", "save time and money")
        prompt = f"""
Write a personalized cold email from {GMAIL_SENDER_NAME} to {company} about our product.

Product: {product_info.get('name', '')}
Description: {product_info.get('description', '')}
Key features: {features}
Their main benefit: {benefit}
Their pain point: {pain_str}
Tone: {tone}
Salutation: {salutation}

Rules:
- MAX 150 words
- Strong hook in first line about THEIR situation (not about us)
- 1-2 sentences on how our product solves their problem
- Specific benefit relevant to {industry} businesses
- Clear CTA (book a call or reply)
- P.S. line with a mini social proof or urgency

Return format:
SUBJECT: [compelling subject line]
BODY:
[email body here]

Sign off as: {GMAIL_SENDER_NAME} | {BUSINESS_NAME}
Calendly: {CALENDLY_LINK}
"""
    else:
        # AI automation mode
        service = research.get("recommended_service", "AI Automation")
        audit_hook = research.get("automation_audit", "")
        roi_proof = research.get("roi_proof_numbers", "")
        ease_hook = research.get("implementation_ease", "")
        social_tone = research.get("social_tone", "")
        
        prompt = f"""
Write a hyper-personalized, high-converting cold email for {company}.

CONTEXT:
- Target Industry: {industry}
- Audit Hook: {audit_hook} (Lead with this!)
- ROI Proof: {roi_proof} (Crucial for value prop)
- Ease of Use: {ease_hook} (To lower friction)
- Social Tone: {social_tone} (Match this vibe!)
- Recommended Service: {service}
- Tone: {tone}

ABOUT {BUSINESS_NAME}:
We help {industry} businesses automate tasks using AI to save time and increase ROI.

STRICT RULES:
1. NO GENERIC SALES SPEAK. Be unique and direct.
2. LEAD with the Observation/Audit Hook.
3. CLEARLY state the ROI (numbers driven).
4. MENTION the ease of implementation (no downtime).
5. MAX 150 words.
6. Casual but professional tone (Pakistani business context).
7. End with a 15-min discovery call CTA.

Return format:
SUBJECT: [unique ROI-driven subject line]
BODY:
[email body]

Sign off as: {GMAIL_SENDER_NAME} | {BUSINESS_NAME}
Book a call: {CALENDLY_LINK}
Website: {WEBSITE}
"""

    raw = ai_call(prompt, temperature=0.8)

    # Parse subject and body
    lines = raw.strip().split("\n")
    subject = ""
    body_lines = []
    in_body = False

    for line in lines:
        if line.upper().startswith("SUBJECT:"):
            subject = line.split(":", 1)[1].strip()
        elif line.upper().startswith("BODY:") or in_body:
            in_body = True
            if not line.upper().startswith("BODY:"):
                body_lines.append(line)

    if not subject:
        subject = f"Quick idea for {company}"
    body = "\n".join(body_lines).strip()
    if not body:
        body = raw  # fallback: use whole response

    return subject, body


def _evaluate_email(body: str) -> bool:
    """Ask AI to self-evaluate the email quality. Return True if good."""
    prompt = f"""
Rate this cold email (1-10) for:
- Personalization, hook strength, value proposition, CTA clarity.

Email:
\"\"\"
{body[:500]}
\"\"\"

Reply with ONLY a number 1-10.
"""
    try:
        score_str = ai_call(prompt, temperature=0.1)
        score = int("".join(filter(str.isdigit, score_str.strip()))[:2])
        return score >= 6
    except Exception:
        return True  # assume ok if eval fails


# ───────────────────────────────────────────────────────────────
# Gmail Sender
# ───────────────────────────────────────────────────────────────

def send_gmail(to_email: str, subject: str, body: str) -> bool:
    """Send email via Gmail SMTP using App Password."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{GMAIL_SENDER_NAME} <{GMAIL_ADDRESS}>"
        msg["To"] = to_email

        # Plain text
        text_part = MIMEText(body, "plain", "utf-8")

        # HTML version with nice formatting
        html_body = body.replace("\n", "<br>")
        html = f"""
<html><body style="font-family: Arial, sans-serif; font-size: 15px; color: #222; max-width: 600px;">
{html_body}
</body></html>"""
        html_part = MIMEText(html, "html", "utf-8")

        msg.attach(text_part)
        msg.attach(html_part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())

        syslog("Email", f"✅ Sent to {to_email} — Subject: {subject[:50]}")
        return True

    except Exception as e:
        syslog("Email", f"❌ Failed to send to {to_email}: {e}", "error")
        return False


# ───────────────────────────────────────────────────────────────
# Main Email Outreach
# ───────────────────────────────────────────────────────────────

def send_outreach_email(lead_id: int, product_info: dict = None, is_followup: bool = False, attempt: int = 1) -> bool:
    """
    Full pipeline: write personalized email → evaluate → send → log.
    """
    lead = get_lead(lead_id)
    if not lead:
        syslog("Email", f"Lead {lead_id} not found", "error")
        return False

    email = lead.get("email", "")
    if not email:
        syslog("Email", f"No email for lead {lead_id} ({lead.get('company')})", "warning")
        return False

    # Load research
    research = {}
    if lead.get("research"):
        try:
            research = json.loads(lead["research"])
        except Exception:
            pass

    # Write email
    subject, body = write_cold_email(lead, research, product_info, is_followup, attempt)

    # Self-evaluate (only for first email, not follow-ups)
    if not is_followup:
        good = _evaluate_email(body)
        if not good:
            syslog("Email", f"Email quality low for {lead.get('company')}, regenerating...")
            subject, body = write_cold_email(lead, research, product_info, is_followup, attempt)

    # Send
    success = send_gmail(email, subject, body)

    # Log to DB
    status = "sent" if success else "failed"
    log_outreach(lead_id, "email", body, subject, status)

    if success:
        update_lead(lead_id, status="contacted", email_valid=1)
        update_deal_stage(lead_id, "contacted")

        # Schedule follow-up
        if not is_followup and attempt < 3:
            followup_date = (datetime.now() + timedelta(days=FOLLOW_UP_DAYS)).isoformat()
            schedule_followup(lead_id, "email", followup_date, attempt + 1)

    return success


def send_batch_emails(lead_ids: list, product_info: dict = None) -> dict:
    """Send emails to a list of leads."""
    sent = 0
    failed = 0
    for lid in lead_ids:
        ok = send_outreach_email(lid, product_info)
        if ok:
            sent += 1
        else:
            failed += 1
    syslog("Email", f"Batch done: {sent} sent, {failed} failed")
    return {"sent": sent, "failed": failed}


if __name__ == "__main__":
    print("📧 Email Agent ready.")
    print("Testing Gmail connection...")
    ok = send_gmail(GMAIL_ADDRESS, "Test from AI Sales System", "Hello! Gmail connection is working. 🎉")
    print("✅ Test email sent!" if ok else "❌ Email failed. Check credentials in config.py")
