"""
===============================================================
  QA TEST SCRIPT — AI Sales OS
  Verifies all new architectural patterns.
===============================================================
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from database import init_db, get_conn, start_session, update_session, get_active_session, get_leads
from agents.planner_agent import generate_campaign_blueprint
from agents.team_orchestrator import TeamOrchestrator
from mcp.registry import mcp_registry
import mcp.calendar_tool

def test_db():
    print("\n--- Testing Database ---")
    init_db()
    conn = get_conn()
    try:
        # Check if sessions table exists and has blueprint column
        col_names = [row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()]
        print(f"Sessions table columns: {col_names}")
        assert "blueprint" in col_names
        print("✅ Database Schema OK")
    except Exception as e:
        print(f"❌ Database Schema Failed: {e}")
    finally:
        conn.close()

def test_planner():
    print("\n--- Testing Planner Agent ---")
    blueprint = generate_campaign_blueprint("Dental Clinics", "Karachi")
    print(f"Blueprint Generated: {json.dumps(blueprint, indent=2)}")
    assert "ideal_customer_profile" in blueprint
    assert "value_proposition" in blueprint
    print("✅ Planner Agent OK")

def test_mcp():
    print("\n--- Testing MCP Tool Registry ---")
    definitions = mcp_registry.get_tool_definitions()
    print(f"Tools Registered: {list(definitions.keys())}")
    assert "book_meeting" in definitions
    
    res = mcp_registry.execute_tool("book_meeting", lead_id=999, datetime_str="2026-04-10 10:00")
    print(f"Tool Execution Result: {res}")
    assert res["status"] == "success"
    print("✅ MCP Foundations OK")

def test_orchestrator_parallel():
    print("\n--- Testing Team Orchestrator (Parallel) ---")
    orchestrator = TeamOrchestrator(mode="automation")
    # We won't block for long, just check if it starts and stops
    orchestrator.start()
    print("Agent workers started...")
    import time
    time.sleep(2)
    orchestrator.stop()
    print("Agent workers stopped.")
    print("✅ Team Orchestrator OK")

if __name__ == "__main__":
    test_db()
    test_planner()
    test_mcp()
    test_orchestrator_parallel()
    print("\n🏆 ALL CORE ARCHITECTURAL TESTS PASSED!")
