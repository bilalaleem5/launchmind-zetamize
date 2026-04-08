"""
===============================================================
  AI SALES SYSTEM — Planner Agent
  Generates strategic campaign blueprints based on target.
===============================================================
"""

import json
from agents.ai_router import ai_call
from database import syslog

def generate_campaign_blueprint(industry, city, product_info=None):
    """
    Creates a strategic roadmap for the campaign.
    """
    context = f"Target Industry: {industry or 'Various'}\nTarget City: {city or 'Global'}\n"
    if product_info:
        context += f"Product: {product_info.get('name')}\nDescription: {product_info.get('description')}\n"
    else:
        context += "Service: AI Automation Agency (ZetaMize)\n"

    prompt = f"""
    You are a Senior Sales Strategist. Create a detailed Campaign Blueprint for an SDR outreach.
    
    {context}
    
    Return a JSON object with the following structure:
    {{
        "ideal_customer_profile": "string",
        "key_pain_points": ["point 1", "point 2"],
        "outreach_strategy": "string",
        "value_proposition": "string",
        "audit_focus": "what specific automation gaps should we look for during research?"
    }}
    
    Response must be ONLY valid JSON.
    """
    
    syslog("Planner", f"Generating blueprint for {industry} in {city}...")
    try:
        response = ai_call(prompt)
        # Clean response if AI adds markdown
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
            
        blueprint = json.loads(response)
        return blueprint
    except Exception as e:
        syslog("Planner", f"Error generating blueprint: {e}", "error")
        return {
            "ideal_customer_profile": "General businesses in the target area.",
            "key_pain_points": ["Manual processes", "Low lead conversion"],
            "outreach_strategy": "Direct value-based outreach via Email and WhatsApp.",
            "value_proposition": "Increase efficiency through AI automation.",
            "audit_focus": "Customer support response time and lead capture forms."
        }
