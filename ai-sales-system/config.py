"""
===============================================================
  AI SALES SYSTEM — Configuration
  Load API keys from environment variables (.env file)
  Copy .env.example to .env and fill in your real values.
===============================================================
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── AI APIs ──────────────────────────────────────────────────
# Set these in your .env file
GEMINI_KEYS = [
    os.getenv("GEMINI_KEY", "your_gemini_key_here"),
]

GROK_KEYS = [
    os.getenv("GROK_KEY", "your_grok_key_here"),
]

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "your_openrouter_key_here")

PRIMARY_AI = "openrouter"   # "gemini" | "grok" | "openrouter"

# ─── Scraping API Keys ────────────────────────────────────────
APOLLO_API_KEY   = os.getenv("APOLLO_API_KEY", "your_apollo_key_here")
RAPIDAPI_KEY     = os.getenv("RAPIDAPI_KEY", "your_rapidapi_key_here")
APIFY_API_KEY    = os.getenv("APIFY_API_KEY", "your_apify_key_here")

# ─── Gmail ────────────────────────────────────────────────────
GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS", "your_email@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "your_app_password_here")
GMAIL_SENDER_NAME  = "LaunchMind MAS"

# ─── Business Info (AI Automation Mode) ───────────────────────
BUSINESS_NAME = "ZetaMize"
BUSINESS_TYPE = "AI Automation Agency"
BUSINESS_DESCRIPTION = """
ZetaMize is an AI automation agency.
We help businesses automate repetitive tasks, streamline operations,
and build AI-powered systems. Services include:
- Custom AI chatbots & virtual assistants
- Business process automation (CRM, invoicing, scheduling)
- AI-powered lead generation & sales pipelines
- WhatsApp & email automation
- Data extraction and reporting automation
"""

FOUNDER_NAME    = "Bilal"
WEBSITE         = "https://zetamize.com"
CALENDLY_LINK   = "https://calendly.com/zetamize"

# ─── Target Lead Criteria (AI Automation mode) ────────────────
TARGET_INDUSTRIES = [
    "restaurants", "clinics", "dental clinics", "real estate agencies",
    "law firms", "accounting firms", "e-commerce stores", "schools",
    "hotels", "salons", "travel agencies", "logistics companies",
    "construction companies", "insurance agencies",
]

TARGET_CITIES = [
    "Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad"
]

# Min fit score (out of 10) to auto-send outreach
MIN_FIT_SCORE = 6

# ─── Outreach Settings ────────────────────────────────────────
FOLLOW_UP_DAYS          = 3    # days before follow-up
MAX_FOLLOW_UPS          = 3    # max follow-ups per lead
EMAIL_DAILY_LIMIT       = 50   # emails per day (stay under spam radar)
WHATSAPP_DELAY_SECONDS  = 8    # seconds between WA messages

# ─── Database ─────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "data", "sales.db")

# ─── Dashboard ────────────────────────────────────────────────
DASHBOARD_PORT = 5000
DASHBOARD_HOST = "127.0.0.1"
