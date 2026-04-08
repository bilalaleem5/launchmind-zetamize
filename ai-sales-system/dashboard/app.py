"""
===============================================================
  AI SALES SYSTEM — Autonomous Dashboard (Flask)
  Everything runs from browser — no terminal needed.
  Background threads run agents automatically.
  Real-time progress via Server-Sent Events (SSE).
===============================================================
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json, threading, queue, time
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for, Response, stream_with_context

from database import (init_db, get_leads, get_lead, get_pipeline_stats, get_outreach,
                      update_lead, update_deal_stage, get_system_logs, get_products,
                      insert_product, get_followups_for_lead, syslog, get_conn,
                      insert_lead, start_session, update_session, get_active_session, get_sessions)
from agents.team_orchestrator import TeamOrchestrator
from agents.planner_agent import generate_campaign_blueprint
from config import DASHBOARD_PORT, DASHBOARD_HOST, MIN_FIT_SCORE

app = Flask(__name__)

# ── Global state for background job ────────────────────────────
_job_status = {
    "running": False,
    "progress": 0,
    "total": 0,
    "phase": "idle",
    "log": [],
}
_sse_clients = []  # list of queues for SSE streaming

def _push_event(data: dict):
    """Push real-time update to all connected browser clients."""
    _job_status["log"].append(data)
    if len(_job_status["log"]) > 200:
        _job_status["log"] = _job_status["log"][-100:]
    for q in list(_sse_clients):
        try:
            q.put_nowait(data)
        except Exception:
            pass

def _set_phase(phase: str, progress: int = None, total: int = None):
    _job_status["phase"] = phase
    if progress is not None:
        _job_status["progress"] = progress
    if total is not None:
        _job_status["total"] = total
    _push_event({"type": "phase", "phase": phase, "progress": _job_status["progress"], "total": _job_status["total"]})

def _log(msg: str, level: str = "info", agent: str = "System"):
    syslog(agent, msg, level)
    _push_event({"type": "log", "level": level, "agent": agent, "msg": msg, "time": datetime.now().strftime("%H:%M:%S")})

# ── Jinja filter ───────────────────────────────────────────────
@app.template_filter('from_json')
def from_json_filter(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return []
    return value or []

# ── Background campaign runner ─────────────────────────────────

def _run_campaign(mode: str, industry: str, city: str, max_leads: int,
                  product_data: dict = None, auto_email: bool = True, auto_wa: bool = True):
    """Full autonomous pipeline: scrape → research → email + WhatsApp → schedule followups."""
    try:
        _job_status["running"] = True
        _job_status["log"] = []
        
        session_id = start_session(industry, city, max_leads)
        _log(f"Campaign Session #{session_id} initialized", agent="System")

        product_id = None
        product_info = None
        keywords = None

        if mode == "product" and product_data:
            pid = insert_product(product_data)
            product_id = pid
            product_info = product_data
            feats = product_data.get("features", [])
            if isinstance(feats, str):
                feats = json.loads(feats)
            keywords = [product_data.get("name", "")] + feats[:2]

        # ── PHASE 0: STRATEGIC PLANNING ───────────────────────
        _set_phase("Generating Strategy", progress=5)
        _log(f"Generating AI strategy for {industry or 'auto'} in {city or 'auto'}...", agent="Planner")
        blueprint = generate_campaign_blueprint(industry, city, product_info)
        update_session(session_id, blueprint=json.dumps(blueprint))
        _log(f"Blueprint generated: {blueprint.get('value_proposition')[:60]}...", agent="Planner")

        # ── START TEAM ORCHESTRATOR ───────────────────────────
        # Starts Research and Outreach workers in background
        orchestrator = TeamOrchestrator(
            mode=mode, 
            product_info=product_info,
            auto_email=auto_email,
            auto_wa=auto_wa,
            log_callback=_log
        )
        orchestrator.start()
        _log("Multi-agent team deployed in parallel", agent="Orchestrator")

        # ── PHASE 1: SCRAPING (Main Thread) ───────────────────
        _set_phase("Scraping Leads", progress=10)
        update_session(session_id, current_step="scraping")
        
        from agents.scraper_agent import run_scraper
        leads_raw = run_scraper(
            mode=mode, industry=industry or None, city=city or None,
            product_id=product_id, product_keywords=keywords,
            max_leads=max_leads
        )
        _log(f"Scraper found {len(leads_raw)} potential leads", agent="Scraper")
        update_session(session_id, total_leads_found=len(leads_raw), current_step="processing")
        
        # Wait for agents to finish their work
        # We poll the DB for any 'new' or 'researched' leads belonging to this session
        _log("Waiting for Research and Outreach agents to complete tasks...", agent="System")
        
        timeout = 600 # 10 minutes max wait
        start_time = time.time()
        while time.time() - start_time < timeout:
            _set_phase("Agents Working...", progress=50) # TBD: Better progress calculation
            # Check if there are still leads to process
            pending_research = get_leads(status="new", mode=mode, limit=1)
            pending_outreach = get_leads(status="researched", mode=mode, limit=1)
            
            if not pending_research and not pending_outreach:
                # Give it a few extra seconds to ensure everything is flushed
                time.sleep(5)
                if not get_leads(status="new", mode=mode, limit=1) and not get_leads(status="researched", mode=mode, limit=1):
                    break
            
            time.sleep(5)

        orchestrator.stop()
        update_session(session_id, status="completed", current_step="done")
        _set_phase("Campaign Complete! ✅", progress=100)
        _log(f"🎉 All agents completed. Final stats: {orchestrator.stats}", agent="System")

    except Exception as e:
        _log(f"Campaign error: {e}", "error", "Campaign")
        if 'session_id' in locals():
            update_session(session_id, status="interrupted", current_step=f"error: {str(e)[:50]}")
        _set_phase(f"Error: {str(e)[:60]}")
    finally:
        _job_status["running"] = False


def _run_followups_bg():
    """Background follow-up runner."""
    try:
        _log("Running scheduled follow-ups...", agent="Followup")
        from agents.followup_agent import run_followups
        stats = run_followups()
        _log(f"Follow-ups done: {stats['sent']} sent, {stats['skipped']} skipped", agent="Followup")
    except Exception as e:
        _log(f"Follow-up error: {e}", "error", "Followup")


# ── Routes ──────────────────────────────────────────────────────

@app.route("/")
def index():
    stats = get_pipeline_stats()
    logs = get_system_logs(limit=15)
    products = get_products()
    recent = get_leads(limit=8)
    
    # Get active session and blueprint
    active_session = get_active_session()
    blueprint = {}
    if active_session and active_session.get("blueprint"):
        try:
            blueprint = json.loads(active_session["blueprint"])
        except Exception:
            pass
            
    job = dict(_job_status)
    return render_template("index.html", stats=stats, logs=logs,
                           products=products, recent=recent, job=job,
                           session=active_session, blueprint=blueprint)


@app.route("/pipeline")
def pipeline():
    stages = ["new","researched","contacted","replied","meeting_booked","closed_won","closed_lost","cold"]
    pipeline_data = {s: get_leads(status=s, limit=50) for s in stages}
    return render_template("pipeline.html", pipeline=pipeline_data, stages=stages)


@app.route("/leads")
def leads():
    status = request.args.get("status")
    mode = request.args.get("mode")
    all_leads = get_leads(status=status, mode=mode, limit=300)
    return render_template("leads.html", leads=all_leads, status=status, mode=mode)


@app.route("/lead/<int:lead_id>")
def lead_detail(lead_id):
    lead = get_lead(lead_id)
    if not lead:
        return redirect(url_for("leads"))
    outreach = get_outreach(lead_id)
    followups = get_followups_for_lead(lead_id)
    research = {}
    pain_points = []
    if lead.get("research"):
        try:
            research = json.loads(lead["research"])
        except Exception:
            pass
    if lead.get("pain_points"):
        try:
            pain_points = json.loads(lead["pain_points"])
        except Exception:
            pass
    return render_template("lead_detail.html", lead=lead, outreach=outreach,
                           followups=followups, research=research, pain_points=pain_points)


@app.route("/lead/<int:lead_id>/update", methods=["POST"])
def update_lead_route(lead_id):
    stage = request.form.get("stage")
    notes = request.form.get("notes", "")
    meeting_at = request.form.get("meeting_at", "")
    if stage:
        update_deal_stage(lead_id, stage, notes=notes, meeting_at=meeting_at)
        update_lead(lead_id, status=stage)
    return redirect(url_for("lead_detail", lead_id=lead_id))


@app.route("/logs")
def logs_page():
    all_logs = get_system_logs(limit=300)
    return render_template("logs.html", logs=all_logs)


# ── Campaign API ────────────────────────────────────────────────

@app.route("/api/campaign/start", methods=["POST"])
def api_start_campaign():
    if _job_status["running"]:
        return jsonify({"ok": False, "error": "Campaign already running!"})

    data = request.get_json()
    mode = data.get("mode", "automation")
    industry = data.get("industry", "").strip()
    city = data.get("city", "").strip()
    max_leads = int(data.get("max_leads", 20))
    auto_email = data.get("auto_email", True)
    auto_wa = data.get("auto_wa", True)
    product_data = data.get("product") if mode == "product" else None

    # Validate product data
    if mode == "product":
        if not product_data or not product_data.get("name"):
            return jsonify({"ok": False, "error": "Product name is required!"})
        # Ensure features is a list
        feats = product_data.get("features", "")
        if isinstance(feats, str):
            product_data["features"] = [f.strip() for f in feats.split(",") if f.strip()]

    t = threading.Thread(
        target=_run_campaign,
        args=(mode, industry, city, max_leads, product_data, auto_email, auto_wa),
        daemon=True
    )
    t.start()
    return jsonify({"ok": True, "message": "Campaign started!"})


@app.route("/api/followups/run", methods=["POST"])
def api_run_followups():
    t = threading.Thread(target=_run_followups_bg, daemon=True)
    t.start()
    return jsonify({"ok": True})


@app.route("/api/followups/due", methods=["GET"])
def api_get_due_followups():
    due = get_due_followups()
    return jsonify(due)


@app.route("/api/archives", methods=["GET"])
def api_campaign_archives():
    sessions = get_sessions()
    return jsonify(sessions)


@app.route("/api/campaign/status")
def api_campaign_status():
    return jsonify(_job_status)


@app.route("/api/events")
def sse_stream():
    """Server-Sent Events — real-time log stream to browser."""
    q = queue.Queue()
    _sse_clients.append(q)

    def generate():
        try:
            # Send current status immediately
            yield f"data: {json.dumps({'type': 'status', 'job': _job_status})}\n\n"
            while True:
                try:
                    event = q.get(timeout=25)
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    yield "data: {\"type\":\"ping\"}\n\n"  # keepalive
        finally:
            _sse_clients.remove(q)

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/stats")
def api_stats():
    return jsonify(get_pipeline_stats())


@app.route("/api/lead/<int:lead_id>/stage", methods=["POST"])
def api_update_stage(lead_id):
    data = request.get_json()
    stage = data.get("stage")
    if stage:
        update_deal_stage(lead_id, stage)
        update_lead(lead_id, status=stage)
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 400


@app.route("/api/gmail/test", methods=["POST"])
def api_test_gmail():
    data = request.get_json()
    gmail_addr = data.get("gmail", "")
    if gmail_addr:
        # Update config dynamically
        import config
        config.GMAIL_ADDRESS = gmail_addr
    try:
        import smtplib
        from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        return jsonify({"ok": True, "message": f"Gmail connected: {GMAIL_ADDRESS}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/gmail/save", methods=["POST"])
def api_save_gmail():
    """Permanently save the Gmail address to config.py."""
    data = request.get_json()
    gmail_addr = data.get("gmail", "").strip()
    if not gmail_addr or "@" not in gmail_addr:
        return jsonify({"ok": False, "error": "Invalid email"})
    # Read and update config.py
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.py")
    with open(config_path, "r") as f:
        content = f.read()
    content = content.replace('GMAIL_ADDRESS      = "YOUR_GMAIL@gmail.com"', f'GMAIL_ADDRESS      = "{gmail_addr}"')
    content = content.replace('GMAIL_ADDRESS = "YOUR_GMAIL@gmail.com"', f'GMAIL_ADDRESS = "{gmail_addr}"')
    with open(config_path, "w") as f:
        f.write(content)
    import config
    config.GMAIL_ADDRESS = gmail_addr
    return jsonify({"ok": True})


@app.route("/api/config", methods=["GET"])
def api_get_config():
    """Retrieve editable config values."""
    import config
    return jsonify({
        "GMAIL_ADDRESS": getattr(config, "GMAIL_ADDRESS", ""),
        "GMAIL_APP_PASSWORD": getattr(config, "GMAIL_APP_PASSWORD", ""),
        "PRIMARY_AI": getattr(config, "PRIMARY_AI", "gemini"),
        "APOLLO_API_KEY": getattr(config, "APOLLO_API_KEY", ""),
        "RAPIDAPI_KEY": getattr(config, "RAPIDAPI_KEY", ""),
        "APIFY_API_KEY": getattr(config, "APIFY_API_KEY", ""),
        "BUSINESS_NAME": getattr(config, "BUSINESS_NAME", ""),
        "FOUNDER_NAME": getattr(config, "FOUNDER_NAME", "")
    })


@app.route("/api/config", methods=["POST"])
def api_save_config():
    """Save config values directly to config.py."""
    data = request.get_json()
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.py")
    
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    import re
    # Helper to replace string vars
    def update_var(var_name, val):
        nonlocal content
        # Matches: VAR_NAME = "something" or VAR_NAME='something'
        pattern = rf'({var_name}\s*=\s*)(["\'])(.*?)\2'
        if re.search(pattern, content):
            content = re.sub(pattern, rf'\1"{val}"', content)
        else:
            # Append if not found
            content += f'\n{var_name} = "{val}"\n'

    if "GMAIL_ADDRESS" in data: update_var("GMAIL_ADDRESS", data["GMAIL_ADDRESS"])
    if "GMAIL_APP_PASSWORD" in data: update_var("GMAIL_APP_PASSWORD", data["GMAIL_APP_PASSWORD"])
    if "PRIMARY_AI" in data: update_var("PRIMARY_AI", data["PRIMARY_AI"])
    if "APOLLO_API_KEY" in data: update_var("APOLLO_API_KEY", data["APOLLO_API_KEY"])
    if "RAPIDAPI_KEY" in data: update_var("RAPIDAPI_KEY", data["RAPIDAPI_KEY"])
    if "APIFY_API_KEY" in data: update_var("APIFY_API_KEY", data["APIFY_API_KEY"])
    if "BUSINESS_NAME" in data: update_var("BUSINESS_NAME", data["BUSINESS_NAME"])
    if "FOUNDER_NAME" in data: update_var("FOUNDER_NAME", data["FOUNDER_NAME"])
    
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return jsonify({"ok": True, "message": "Config updated successfully. Requires app restart to apply globally."})


@app.route("/api/inbox", methods=["GET"])
def api_inbox():
    """Fetch leads that have replied for the Smart Inbox."""
    replied_leads = get_leads(status="replied", limit=50)
    return jsonify(replied_leads)


@app.route("/api/brain/upload", methods=["POST"])
def api_brain_upload():
    if 'file' not in request.files:
        return jsonify({"ok": False, "error": "No file part"})
    file = request.files['file']
    if file.filename == '':
        return jsonify({"ok": False, "error": "No selected file"})
        
    brain_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "brain")
    os.makedirs(brain_dir, exist_ok=True)
    
    filepath = os.path.join(brain_dir, file.filename)
    file.save(filepath)
    return jsonify({"ok": True, "message": "File indexed successfully"})


@app.route("/api/brain/files", methods=["GET"])
def api_brain_files():
    brain_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "brain")
    files = []
    if os.path.exists(brain_dir):
        for f in os.listdir(brain_dir):
            if os.path.isfile(os.path.join(brain_dir, f)):
                files.append({"name": f})
    return jsonify(files)


if __name__ == "__main__":
    init_db()
    print(f"\n{'='*55}")
    print(f"  🤖 ZetaMize AI Sales System — Dashboard")
    print(f"  Open browser: http://localhost:{DASHBOARD_PORT}")
    print(f"{'='*55}\n")
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False, threaded=True)
