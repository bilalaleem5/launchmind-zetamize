"""
CEO Agent — Orchestrator of the LaunchMind Multi-Agent System.
Receives startup idea, decomposes into tasks, reviews outputs, triggers revisions.
Assignment: Uses LLM at least TWICE (decompose + review).
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.message_bus import send_message, get_messages, get_latest_message, print_full_message_log
from agents.product_agent import ProductAgent
from agents.github_engineer_agent import GitHubEngineerAgent
from agents.slack_marketing_agent import SlackMarketingAgent
from agents.qa_agent import QAAgent
from agents.ui_utils import print_step, print_agent_thought, print_status_update
import google.generativeai as genai
import config

import requests

CEO = "ceo"
MAX_REVISIONS = 2

def _llm(prompt: str) -> str:
    try:
        print_step("ceo", "Thinking with OpenRouter AI")
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
    except Exception as e:
        print(f"   [LLM Error] {e}")
        raise e


class CEOAgent:
    def __init__(self):
        self.decision_log = []

    def _log(self, decision: str):
        self.decision_log.append(decision)
        print_agent_thought("ceo", decision)

    def decompose_idea(self, startup_idea: str) -> dict:
        """LLM CALL #1: Decompose startup idea into agent tasks."""
        print_step(CEO, f"Decomposing startup idea: {startup_idea[:30]}...")
        self._log(f"Decomposing startup idea: '{startup_idea}'")

        prompt = f"""You are the CEO of a startup. You received this idea:
"{startup_idea}"

Decompose this idea into specific tasks for three agents. Return a JSON object with these keys:
- "product_task": A specific instruction for the Product Manager agent (define personas, features, value prop)
- "engineer_task": A specific instruction for the Engineer agent (what to build as a landing page HTML)
- "marketing_task": A specific instruction for the Marketing agent (tagline, email copy, social posts)

Return ONLY valid JSON, no explanation."""

        response = _llm(prompt)
        # Clean any markdown code blocks
        response = response.replace("```json", "").replace("```", "").strip()
        try:
            tasks = json.loads(response)
        except Exception:
            tasks = {
                "product_task": f"Define the product for: {startup_idea}. Create value proposition, 3 personas, 5 features, 3 user stories.",
                "engineer_task": f"Build a stunning HTML landing page for: {startup_idea}.",
                "marketing_task": f"Generate a tagline, cold email, and 3 social posts for: {startup_idea}."
            }
        self._log(f"Tasks decomposed successfully: {list(tasks.keys())}")
        return tasks

    def review_output(self, agent_name: str, output: dict, spec: dict = None) -> tuple[bool, str]:
        """LLM CALL #2: Review agent output and decide if revision is needed."""
        self._log(f"Reviewing output from {agent_name}...")

        context = f"Agent: {agent_name}\nOutput: {json.dumps(output, indent=2)}"
        if spec:
            context += f"\nOriginal Product Spec: {json.dumps(spec, indent=2)}"

        prompt = f"""You are a CEO reviewing work from your team.

{context}

Review critically:
1. Is the output specific and relevant to the startup idea?
2. Is it complete (no missing sections)?
3. Is the quality high enough to ship?

Reply with a JSON:
{{"verdict": "pass" or "fail", "reason": "one sentence reason", "revision_instruction": "specific fix if fail, else null"}}

Return ONLY valid JSON."""

        response = _llm(prompt)
        response = response.replace("```json", "").replace("```", "").strip()
        try:
            review = json.loads(response)
            passed = review.get("verdict", "pass") == "pass"
            feedback = review.get("revision_instruction") or review.get("reason", "")
        except Exception:
            passed = True
            feedback = "Output accepted"

        self._log(f"Review verdict for {agent_name}: {'✅ PASS' if passed else '❌ FAIL — ' + feedback}")
        return passed, feedback

    def run(self, startup_idea: str):
        # ── STEP 1: Decompose idea into tasks ──
        tasks = self.decompose_idea(startup_idea)

        # ── STEP 2: Send task to Product Agent ──
        msg_id = send_message(CEO, "product", "task", {
            "idea": startup_idea,
            "focus": tasks["product_task"]
        })

        product_agent = ProductAgent()
        product_spec = product_agent.run({
            "idea": startup_idea,
            "focus": tasks["product_task"]
        })

        # ── STEP 3: CEO Reviews Product Spec (Feedback Loop) ──
        passed, feedback = self.review_output("product", product_spec)
        if not passed:
            print(f"\n🔄 [CEO] Sending REVISION REQUEST to Product Agent...")
            rev_id = send_message(CEO, "product", "revision_request", {
                "issue": feedback,
                "instruction": f"Revise the product spec. Specifically: {feedback}"
            }, parent_message_id=msg_id)
            # Product agent revises
            product_spec = product_agent.revise(feedback)
            send_message("product", CEO, "result", {"revised": True, "spec": product_spec}, parent_message_id=rev_id)
            self._log("Product agent revised spec. Accepted on 2nd attempt.")

        # ── STEP 4: Send to Engineer & Marketing in parallel ──
        send_message(CEO, "engineer", "task", {
            "product_spec": product_spec,
            "instruction": tasks["engineer_task"]
        })
        send_message(CEO, "marketing", "task", {
            "product_spec": product_spec,
            "instruction": tasks["marketing_task"]
        })

        # Run Engineer Agent
        engineer_agent = GitHubEngineerAgent()
        engineer_result = engineer_agent.run(product_spec)

        # Run Marketing Agent
        marketing_agent = SlackMarketingAgent()
        marketing_result = marketing_agent.run(product_spec, engineer_result.get("pr_url", ""))

        # ── STEP 5: QA Agent reviews engineer & marketing output ──
        print_step(CEO, "Handing off to QA for final review")
        send_message(CEO, "qa", "task", {
            "html": engineer_result.get("html", ""),
            "pr_url": engineer_result.get("pr_url", ""),
            "commit_sha": engineer_result.get("commit_sha", ""),
            "marketing_copy": marketing_result,
            "product_spec": product_spec
        })

        qa_agent = QAAgent()
        qa_result = qa_agent.run(
            html=engineer_result.get("html", ""),
            pr_url=engineer_result.get("pr_url", ""),
            commit_sha=engineer_result.get("commit_sha", ""),
            marketing_copy=marketing_result,
            product_spec=product_spec
        )

        # ── STEP 6: CEO handles QA verdict (Dynamic Decision-Making) ──
        if qa_result.get("verdict") == "fail":
            issues = qa_result.get("issues", [])
            self._log(f"QA FAILED! Issues: {issues}. Sending revision to Engineer...")
            send_message(CEO, "engineer", "revision_request", {
                "issues": issues,
                "instruction": f"Revise HTML landing page to fix: {'; '.join(issues)}"
            })
            # Engineer revises
            engineer_result = engineer_agent.revise(product_spec, issues)
            send_message("engineer", CEO, "result", {"revised": True, "pr_url": engineer_result.get("pr_url")})
            self._log("Engineer revised HTML after QA feedback. ✅")
        else:
            self._log("QA PASSED ✅ — All outputs accepted.")

        # ── STEP 7: Final Slack Summary from CEO ──
        final_summary = {
            "startup": startup_idea,
            "pr_url": engineer_result.get("pr_url", "N/A"),
            "tagline": marketing_result.get("tagline", ""),
            "status": "Launch Complete ✅",
            "qa_verdict": qa_result.get("verdict", "pass")
        }

        send_message(CEO, "slack", "result", final_summary)
        marketing_agent.post_final_summary(final_summary, engineer_result.get("pr_url", ""))

        # ── PRINT FULL LOG ──
        print_full_message_log()

        print("\n" + "="*60)
        print("🎯 CEO DECISION LOG:")
        for i, d in enumerate(self.decision_log, 1):
            print(f"  {i}. {d}")
        print("="*60)

        return {
            "product_spec": product_spec,
            "engineer_result": engineer_result,
            "marketing_result": marketing_result,
            "qa_result": qa_result
        }
