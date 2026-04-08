"""
LaunchMind — Multi-Agent AI Startup Launcher
Entry point for the MAS assignment submission.

Usage:
    python main.py
    OR
    cd ai-sales-system && python mas_main.py

This file provides the top-level entry point as required by the assignment rubric.
"""

import sys
import os

# Add the ai-sales-system directory to path so its modules resolve correctly
AI_SYSTEM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai-sales-system")
sys.path.insert(0, AI_SYSTEM_DIR)

# Change working directory so relative paths inside mas_main work correctly
os.chdir(AI_SYSTEM_DIR)

# Import and run
from mas_main import main

if __name__ == "__main__":
    main()
