"""
===============================================================
  AI SALES SYSTEM — Team Orchestrator
  Manages parallel execution of specialized agents.
===============================================================
"""

import threading
import time
import queue
from database import get_leads, syslog, get_lead
from agents.research_agent import research_lead
from agents.email_agent import send_outreach_email
from agents.whatsapp_agent import send_whatsapp_outreach
from config import MIN_FIT_SCORE

class TeamOrchestrator:
    def __init__(self, mode="automation", product_info=None, auto_email=True, auto_wa=True, log_callback=None):
        self.mode = mode
        self.product_info = product_info
        self.auto_email = auto_email
        self.auto_wa = auto_wa
        self.log_callback = log_callback
        self.running = False
        self.stop_event = threading.Event()
        
        # Stats
        self.stats = {
            "researched": 0,
            "qualified": 0,
            "emailed": 0,
            "whatsapped": 0
        }

    def _log(self, msg, level="info", agent="Orchestrator"):
        syslog(agent, msg, level)
        if self.log_callback:
            self.log_callback(msg, level, agent)

    def research_worker(self):
        """Worker that picks up 'new' leads and researches them."""
        self._log("Research Agent started", agent="Research")
        while not self.stop_event.is_set():
            leads = get_leads(status="new", mode=self.mode, limit=5)
            if not leads:
                time.sleep(2)
                continue
            
            for lead in leads:
                if self.stop_event.is_set(): break
                try:
                    self._log(f"Analyzing {lead['company']}", agent="Research")
                    result = research_lead(lead["id"], self.product_info)
                    self.stats["researched"] += 1
                    if result.get("fit_score", 0) >= MIN_FIT_SCORE:
                        self.stats["qualified"] += 1
                        self._log(f"Lead qualified: {lead['company']} ({result['fit_score']}/10)", agent="Research")
                except Exception as e:
                    self._log(f"Research error for {lead['company']}: {e}", "error", "Research")
            
            time.sleep(1)

    def outreach_worker(self):
        """Worker that picks up 'researched' leads and sends outreach."""
        self._log("Outreach Agent started", agent="Outreach")
        while not self.stop_event.is_set():
            leads = get_leads(status="researched", mode=self.mode, limit=5)
            # Only process leads with a valid fit score above threshold
            target_leads = [l for l in leads if (l.get("fit_score") or 0) >= MIN_FIT_SCORE]
            
            if not target_leads:
                time.sleep(3)
                continue

            for lead in target_leads:
                if self.stop_event.is_set(): break
                
                # Email Outreach
                if self.auto_email and lead.get("email"):
                    try:
                        self._log(f"Sending email to {lead['company']}", agent="Outreach")
                        ok = send_outreach_email(lead["id"], self.product_info)
                        if ok: self.stats["emailed"] += 1
                    except Exception as e:
                        self._log(f"Email error for {lead['company']}: {e}", "error", "Outreach")

                # WhatsApp Outreach
                if self.auto_wa and lead.get("phone"):
                    try:
                        self._log(f"Sending WhatsApp to {lead['company']}", agent="Outreach")
                        ok = send_whatsapp_outreach(lead["id"], self.product_info)
                        if ok: self.stats["whatsapped"] += 1
                    except Exception as e:
                        self._log(f"WhatsApp error for {lead['company']}: {e}", "error", "Outreach")
                
                # Update status if not already updated by agents
                # (agents usually update status to 'contacted')
            
            time.sleep(2)

    def start(self):
        self.running = True
        self.stop_event.clear()
        self.t_research = threading.Thread(target=self.research_worker, daemon=True)
        self.t_outreach = threading.Thread(target=self.outreach_worker, daemon=True)
        self.t_research.start()
        self.t_outreach.start()

    def stop(self):
        self.stop_event.set()
        self.running = False
        if hasattr(self, 't_research'): self.t_research.join(timeout=2)
        if hasattr(self, 't_outreach'): self.t_outreach.join(timeout=2)
        self._log("All agents stopped", agent="System")
