"""
===============================================================
  AI SALES SYSTEM — Follow-up Agent
  Checks scheduled follow-ups and executes them automatically
===============================================================
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from database import (get_due_followups, mark_followup_done, get_lead,
                      update_lead, get_outreach, syslog, get_product)
from agents.email_agent import send_outreach_email
from agents.whatsapp_agent import send_whatsapp_outreach
from config import MAX_FOLLOW_UPS
from mcp.registry import mcp_registry
import mcp.calendar_tool # Ensure tool is registered


def run_followups() -> dict:
    """
    Check all due follow-ups and execute them.
    Returns stats dict.
    """
    due = get_due_followups()
    syslog("Followup", f"Found {len(due)} due follow-ups")

    stats = {"processed": 0, "sent": 0, "skipped": 0, "maxed": 0}

    for fu in due:
        lead_id = fu["lead_id"]
        channel = fu["channel"]
        attempt = fu.get("attempt_number", 1)
        company = fu.get("company", f"Lead {lead_id}")

        # Check if lead has already replied or closed
        lead = get_lead(lead_id)
        if not lead:
            mark_followup_done(fu["id"])
            continue

        status = lead.get("status", "")
        if status in ("replied", "meeting_booked", "closed_won", "closed_lost"):
            syslog("Followup", f"Skipping {company} — status: {status}")
            mark_followup_done(fu["id"])
            stats["skipped"] += 1
            continue

        # Check max follow-ups
        all_outreach = get_outreach(lead_id)
        channel_count = sum(1 for o in all_outreach if o["channel"] == channel)
        if channel_count >= MAX_FOLLOW_UPS + 1:
            syslog("Followup", f"Max follow-ups reached for {company} ({channel})")
            update_lead(lead_id, status="cold")
            mark_followup_done(fu["id"])
            stats["maxed"] += 1
            continue

        # Load product info if product mode
        product_info = None
        product_id = lead.get("product_id")
        if product_id:
            product_info = get_product(product_id)

        # Send follow-up
        syslog("Followup", f"Follow-up #{attempt} → {company} via {channel}")
        success = False

        try:
            if channel == "email":
                success = send_outreach_email(lead_id, product_info, is_followup=True, attempt=attempt)
            elif channel == "whatsapp":
                success = send_whatsapp_outreach(lead_id, product_info, is_followup=True, attempt=attempt)
        except Exception as e:
            syslog("Followup", f"Error sending follow-up to {company}: {e}", "error")

        mark_followup_done(fu["id"])
        stats["processed"] += 1
        if success:
            stats["sent"] += 1

    syslog("Followup", f"Done: {stats['sent']} sent, {stats['skipped']} skipped, {stats['maxed']} maxed out")
    return stats


def mark_lead_replied(lead_id: int, notes: str = ""):
    """Call this when a lead replies to any message."""
    from database import update_deal_stage, update_lead
    update_lead(lead_id, status="replied")
    update_deal_stage(lead_id, "replied", notes=notes)
    syslog("Followup", f"Lead {lead_id} marked as replied")


def mark_meeting_booked(lead_id: int, meeting_datetime: str = None, notes: str = ""):
    """Call this when a meeting is booked."""
    from database import update_deal_stage, update_lead
    update_lead(lead_id, status="meeting_booked")
    update_deal_stage(lead_id, "meeting_booked", notes=notes, meeting_at=meeting_datetime)
    syslog("Followup", f"Lead {lead_id} — MEETING BOOKED! {meeting_datetime or ''}")
    
    # ── MCP TOOL EXECUTION ──────────────────────────────────
    if meeting_datetime:
        try:
            res = mcp_registry.execute_tool("book_meeting", lead_id=lead_id, datetime_str=meeting_datetime)
            if res.get("status") == "success":
                syslog("MCP", f"Meeting synced to Google Calendar: {res.get('link')}")
                # Update notes with meeting link
                update_deal_stage(lead_id, "meeting_booked", notes=f"{notes}\nCal Link: {res.get('link')}")
        except Exception as e:
            syslog("MCP", f"Tool execution failed: {e}", "error")


def mark_deal_closed(lead_id: int, won: bool = True, notes: str = ""):
    """Mark deal as won or lost."""
    from database import update_deal_stage, update_lead
    stage = "closed_won" if won else "closed_lost"
    status = "closed_won" if won else "closed_lost"
    update_lead(lead_id, status=status)
    update_deal_stage(lead_id, stage, notes=notes)
    syslog("Followup", f"Lead {lead_id} — {'WON 🎉' if won else 'LOST 😔'}")


if __name__ == "__main__":
    print("🔄 Running follow-up agent...")
    stats = run_followups()
    print(f"Results: {stats}")
