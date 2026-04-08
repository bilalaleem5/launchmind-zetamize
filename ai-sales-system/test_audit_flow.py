import json
from agents.research_agent import research_lead
from database import init_db, insert_lead, get_lead

init_db()

# Create a test lead for a local clinic
test_lead = {
    "company": "Test Dental Clinic Karachi",
    "website": "https://example-clinic.com", # AI will probably hallucinate some gaps based on industry if site not real
    "industry": "dental clinics",
    "city": "Karachi",
    "mode": "automation"
}
lid = insert_lead(test_lead)

print(f"--- Researching Lead ID: {lid} ---")
result = research_lead(lid)

print("\n--- AI AUTOMATION AUDIT RESULTS ---")
print(f"Detected Industry: {result.get('industry')}")
print(f"Automation Audit Hook: {result.get('automation_audit')}")
print(f"Suggested Workflow: {result.get('suggested_workflow')}")
print(f"Fit Score: {result.get('fit_score')}/10")

# Test Email Generation
from agents.email_agent import write_cold_email
lead_data = get_lead(lid)
subject, body = write_cold_email(lead_data, result)

print("\n--- GENERATED EMAIL PREVIEW ---")
print(f"Subject: {subject}")
print("-" * 30)
print(body)
