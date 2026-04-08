"""
Slack Marketing Agent — Generates marketing copy and sends real Slack messages + Emails.
"""
import json
import os
import sys
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.message_bus import send_message, get_latest_message
import config
from agents.ui_utils import print_step, print_status_update

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

AGENT = "marketing"
SLACK_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")


def _llm(prompt: str) -> str:
    print_step("marketing", "Drafting Campaigns (Llama 3)")
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    data = {"model": "meta-llama/llama-3.3-70b-instruct", "messages": [{"role": "user", "content": prompt}]}
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
    return r.json()["choices"][0]["message"]["content"].strip()


class SlackMarketingAgent:
    def _generate_copy(self, spec: dict) -> dict:
        prompt = f"""You are a Growth Marketing Manager. Based on this product spec:
{json.dumps(spec, indent=2)}

Generate:
1. "tagline": A catchy product tagline (under 10 words)
2. "description": A short product description (2-3 sentences)
3. "email_subject": Subject for a cold outreach email
4. "email_body": HTML body for the cold outreach email
5. "social_posts": String array of 3 social media drafts

Return ONLY a valid JSON object."""

        response = _llm(prompt)
        response = response.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(response)
        except Exception:
            return {
                "tagline": "Automate your sales pipeline effortlessly.",
                "description": "ZetaMize AI Sales OS finds and emails leads automatically.",
                "email_subject": "Automate your lead generation today",
                "email_body": "<p>Hi there,</p><p>We can help you automate sales. Reply to book a call.</p>",
                "social_posts": ["Just launched our new AI sales agent! #AI #Sales", "Stop manual prospecting.", "Try ZetaMize today."]
            }

    def _send_email(self, subject: str, html_body: str, to_email: str):
        print(f"   📧 Sending real email to {to_email}...")
        try:
            msg = MIMEMultipart()
            msg['From'] = f"{config.GMAIL_SENDER_NAME} <{config.GMAIL_ADDRESS}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(html_body, 'html'))

            server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
            server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            server.sendmail(config.GMAIL_ADDRESS, to_email, msg.as_string())
            server.quit()
            print("   ✅ Email sent successfully.")
        except Exception as e:
            print(f"   ❌ Email failed: {e}")

    def post_final_summary(self, summary_info: dict, pr_url: str):
        """Used by CEO at the very end to post Block Kit message to Slack."""
        if not SLACK_TOKEN:
            print("⚠️ [MARKETING] Warning: SLACK_BOT_TOKEN not found. Skipping Slack post.")
            return

        tagline = summary_info.get("tagline", "New Launch")
        desc = f"We just finished a full MAS run for: {summary_info.get('startup', 'Unknown')}"

        payload = {
            "channel": "#launches",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🚀 LaunchMind Startup Shipped: " + tagline}
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": desc}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*GitHub PR:* <{pr_url}|View PR>"},
                        {"type": "mrkdwn", "text": f"*QA Status:* {summary_info.get('qa_verdict', 'pass').upper()}"}
                    ]
                }
            ]
        }
        
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {SLACK_TOKEN}"},
            json=payload
        )
        if r.status_code == 200 and r.json().get("ok"):
            print("   💬 Slack message posted successfully via Block Kit!")
        else:
            print(f"   ❌ Slack API Error: {r.text}")

    def run(self, spec: dict, pr_url: str = "") -> dict:
        print_step("marketing", "Launching Marketing Campaign")
        
        # Step 1: Generate Copy
        copy = self._generate_copy(spec)
        print_status_update("Marketing copy generated.")

        # Step 2: Send Email
        self._send_email(
            subject=f"Exciting News: {copy.get('tagline')}",
            html_body=copy.get('email_body', ''),
            to_email="sales.zetamize@gmail.com"
        )
        print_status_update("Email sent via Gmail SMTP.")

        # Step 3: Post to Slack
        self.post_final_summary(copy, pr_url)
        print_status_update("Slack notification posted to #launches.")

        # Return to CEO
        send_message(AGENT, "ceo", "result", copy)
        return copy
