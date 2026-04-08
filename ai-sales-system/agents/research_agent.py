"""
===============================================================
  AI SALES SYSTEM — Research Agent
  Analyzes company websites + generates fit score
  Uses: Gemini/Grok/OpenRouter AI
===============================================================
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests, json
from bs4 import BeautifulSoup
from agents.ai_router import ai_json
from database import update_lead, get_lead, syslog, insert_lead
from config import BUSINESS_DESCRIPTION, BUSINESS_NAME
from agents.scraper_agent import scrape_instagram_business, scrape_threads_presence, find_similar_linkedin_companies

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

def _scrape_website_text(url: str, max_chars: int = 3000) -> str:
    """Extract readable text from a company website."""
    if not url or not url.startswith("http"):
        return ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        # Remove scripts and styles
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return text[:max_chars]
    except Exception:
        return ""


def research_lead(lead_id: int, product_info: dict = None) -> dict:
    """
    Full research pipeline for a lead.
    product_info: dict with name, description, features (for product mode)
    Returns the research result dict.
    """
    lead = get_lead(lead_id)
    if not lead:
        syslog("Research", f"Lead {lead_id} not found", "error")
        return {}

    company = lead.get("company", "")
    website = lead.get("website", "")
    industry = lead.get("industry", "")
    mode = lead.get("mode", "automation")

    syslog("Research", f"Researching: {company}")

    # Step 1: Scrape website text
    web_text = _scrape_website_text(website)

    # Step 1.5: Social Discovery (Phase 8)
    social_data = {}
    if "instagram.com" in website or company.lower().replace(" ","") in website:
        social_data["instagram"] = scrape_instagram_business(company.lower().replace(" ",""))
    if "threads.net" in website:
        social_data["threads"] = scrape_threads_presence(website)
    
    # Check for LinkedIn similar companies if this is a high-fit B2B lead
    similar_leads = []
    if "linkedin.com/company" in website:
        similar_raw = find_similar_linkedin_companies(website)
        for s in similar_raw:
            similar_leads.append(s.get("name"))

    # Step 2: Build analysis prompt
    if mode == "automation" or not product_info:
        context = f"""
You are a senior sales analyst for {BUSINESS_NAME}, an AI automation agency.

COMPANY TO ANALYZE:
- Name: {company}
- Industry: {industry}
- Website: {website}
- Website Content: {web_text if web_text else 'Not available'}

OUR SERVICES:
{BUSINESS_DESCRIPTION}

SOCIAL DISCOVERY:
{json.dumps(social_data) if social_data else 'None found'}

Analyze this company and return a JSON with these exact fields:
{{
  "industry": "detected industry",
  "company_size": "micro/small/medium/large",
  "digital_presence": "poor/basic/moderate/strong",
  "social_tone": "The vibe from their IG/Threads (e.g., 'Energetic and youth-focused')",
  "automation_audit": "A specific 1-sentence observation about a gap in their current workflow or website that could be automated (e.g., 'I noticed your booking process is still manual, which might be causing lead drop-off'). THIS IS THE HOOK.",
  "roi_proof_numbers": "A specific ROI calculation (e.g., 'Automating this could save ~15 hours/week, roughly $2000/mo in overhead')",
  "implementation_ease": "How easy it is for them (e.g., 'Plug-and-play solution, setup in 48 hours with zero downtime')",
  "pain_points": ["list of 3-5 specific automation pain points this company likely has"],
  "fit_score": 7,
  "personalization_hooks": ["2-3 specific things to mention in outreach, including social proof if found"],
  "recommended_service": "specific AI/Automation service that fits best",
  "suggested_workflow": "A 1-sentence description of a specific AI workflow we could build for them",
  "outreach_tone": "formal/semi-formal/casual",
  "fit_reason": "one sentence why they are/aren't a good fit"
}}
"""
    else:
        # Product mode
        features_str = "\n".join(f"- {f}" for f in product_info.get("features", []))
        context = f"""
You are a sales analyst. Analyze this company as a potential buyer for our product.

COMPANY TO ANALYZE:
- Name: {company}
- Industry: {industry}
- Website Content: {web_text if web_text else 'Not available'}

OUR PRODUCT:
- Name: {product_info.get('name', '')}
- Description: {product_info.get('description', '')}
- Key Features:
{features_str}
- Target Audience: {product_info.get('target_audience', '')}

Return a JSON with these exact fields:
{{
  "industry": "detected industry",
  "company_size": "micro/small/medium/large",
  "pain_points": ["list of 3-5 pain points our product solves for them"],
  "fit_score": 7,  // 1-10, product fit score
  "personalization_hooks": ["2-3 specific things to mention"],
  "key_benefit_for_them": "the #1 benefit of our product for this specific company",
  "outreach_tone": "formal/semi-formal/casual",
  "fit_reason": "one sentence why they are/aren't a good fit"
}}
"""

    try:
        result = ai_json(context)
    except Exception as e:
        syslog("Research", f"AI failed for {company}: {e}", "warning")
        result = {
            "industry": industry,
            "company_size": "unknown",
            "pain_points": ["Manual processes", "No digital automation"],
            "fit_score": 5,
            "personalization_hooks": [f"Your {industry} business", "Growth opportunities"],
            "recommended_service": "AI Automation Consultation",
            "outreach_tone": "semi-formal",
            "fit_reason": "Potential AI automation client",
        }

    # Save to DB
    update_lead(lead_id,
        research=json.dumps(result),
        pain_points=json.dumps(result.get("pain_points", [])),
        fit_score=result.get("fit_score", 5),
        status="researched"
    )

    syslog("Research", f"✅ {company} — fit_score={result.get('fit_score',0)}/10")
    return result


def research_batch(lead_ids: list, product_info: dict = None) -> list[dict]:
    """Research multiple leads in sequence."""
    results = []
    for lid in lead_ids:
        try:
            r = research_lead(lid, product_info)
            results.append({"lead_id": lid, **r})
        except Exception as e:
            syslog("Research", f"Failed for lead {lid}: {e}", "error")
    return results


if __name__ == "__main__":
    print("🧠 Research Agent ready. Use research_lead(lead_id) to analyze a lead.")
