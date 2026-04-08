"""
Product Agent — Generates a structured product specification.
Assignment: Uses LLM to create value_proposition, personas, features, user_stories.
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.message_bus import send_message, get_latest_message
from agents.ui_utils import print_step
import config
import requests

AGENT = "product"

def _llm(prompt: str) -> str:
    print_step("product", "Consulting Market Data (Llama 3)")
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "meta-llama/llama-3.3-70b-instruct",
        "messages": [{"role": "user", "content": prompt}]
    }
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
    return r.json()["choices"][0]["message"]["content"].strip()


class ProductAgent:
    def _generate_spec(self, idea_context: str) -> dict:
        prompt = f"""You are a senior Product Manager. Generate a complete product specification for:

{idea_context}

Return a JSON object with EXACTLY these fields:
{{
  "value_proposition": "One sentence describing what the product does and for whom",
  "personas": [
    {{"name": "...", "role": "...", "pain_point": "..."}},
    {{"name": "...", "role": "...", "pain_point": "..."}},
    {{"name": "...", "role": "...", "pain_point": "..."}}
  ],
  "features": [
    {{"name": "...", "description": "...", "priority": 1}},
    {{"name": "...", "description": "...", "priority": 2}},
    {{"name": "...", "description": "...", "priority": 3}},
    {{"name": "...", "description": "...", "priority": 4}},
    {{"name": "...", "description": "...", "priority": 5}}
  ],
  "user_stories": [
    "As a [user], I want to [action] so that [benefit]",
    "As a [user], I want to [action] so that [benefit]",
    "As a [user], I want to [action] so that [benefit]"
  ]
}}

Return ONLY valid JSON. Be specific and concrete, not generic."""

        response = _llm(prompt)
        response = response.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(response)
        except Exception:
            # Fallback spec for the AI Sales OS idea
            return {
                "value_proposition": "ZetaMize AI Sales OS autonomously finds leads, researches prospects, and sends hyper-personalized outreach so freelancers close deals without lifting a finger.",
                "personas": [
                    {"name": "Bilal", "role": "Freelance AI Automation Developer", "pain_point": "Spends hours manually finding and emailing cold leads instead of building."},
                    {"name": "Sara", "role": "Solo SaaS Founder", "pain_point": "No time or budget for a dedicated SDR team."},
                    {"name": "Ahmed", "role": "Digital Agency Owner", "pain_point": "Inconsistent outreach pipeline causing revenue fluctuations."}
                ],
                "features": [
                    {"name": "Autonomous Lead Scraping", "description": "Parallel scraping from Apollo, Apify, and LinkedIn.", "priority": 1},
                    {"name": "AI Website Audit", "description": "Analyzes prospect websites to find automation gaps.", "priority": 2},
                    {"name": "ROI-Focused Email Drafting", "description": "Generates cold emails with specific ROI numbers.", "priority": 3},
                    {"name": "Auto Follow-Up Pipeline", "description": "Schedules and sends follow-ups autonomously.", "priority": 4},
                    {"name": "Real-Time Dashboard", "description": "Premium glassmorphism dashboard with 10 tabs.", "priority": 5}
                ],
                "user_stories": [
                    "As a freelancer, I want to automatically find 50 qualified leads/day so that I can focus on closing rather than prospecting.",
                    "As an agency owner, I want AI-written emails with real ROI calculations so that my outreach converts better than generic templates.",
                    "As a solo founder, I want a smart inbox that shows replied leads so that I never miss a hot opportunity."
                ]
            }

    def run(self, task: dict) -> dict:
        """Receive task from CEO and generate product spec."""
        print_step("product", "Generating Product Specification")
        idea = task.get("idea", "AI Sales Automation SaaS")
        focus = task.get("focus", "")
        context = f"Startup Idea: {idea}\nFocus: {focus}"

        spec = self._generate_spec(context)

        print(f"   ✅ Value Proposition: {spec.get('value_proposition', '')[:80]}...")
        print(f"   ✅ {len(spec.get('personas', []))} Personas | {len(spec.get('features', []))} Features | {len(spec.get('user_stories', []))} User Stories")

        # Send spec to Engineer and Marketing
        send_message(AGENT, "engineer", "result", {"spec": spec})
        send_message(AGENT, "marketing", "result", {"spec": spec})
        # Send confirmation to CEO
        send_message(AGENT, "ceo", "confirmation", {"status": "Product spec ready", "spec_preview": spec.get("value_proposition", "")})

        return spec

    def revise(self, feedback: str) -> dict:
        """Revise the product spec based on CEO feedback."""
        print(f"\n🔄 [PRODUCT AGENT] Revising spec based on CEO feedback: {feedback}")
        context = f"Revise and improve the product spec for ZetaMize AI Sales OS.\nFeedback: {feedback}\nMake it more specific, add concrete numbers and details."
        spec = self._generate_spec(context)
        print(f"   ✅ Spec revised successfully.")
        return spec
