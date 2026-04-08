"""
===============================================================
  AI SALES SYSTEM — Calendar Tool (MCP-like)
  Simulates calendar booking for the Sales system.
===============================================================
"""

from mcp.registry import mcp_registry
from database import syslog

def book_meeting(lead_id, datetime_str, duration_min=30):
    """
    Simulates booking a meeting on Google Calendar.
    In the future, this will use the actual Google Calendar API.
    """
    syslog("MCP", f"Booking meeting for Lead #{lead_id} at {datetime_str}...")
    # Simulated logic
    success = True
    if success:
        return {"status": "success", "event_id": "cal_12345", "link": "https://meet.google.com/abc-defg-hij"}
    return {"status": "failed", "error": "Conflict detected"}

# Register the tool
mcp_registry.register_tool(
    name="book_meeting",
    description="Book a sales meeting/demo with a lead in Google Calendar.",
    func=book_meeting
)
