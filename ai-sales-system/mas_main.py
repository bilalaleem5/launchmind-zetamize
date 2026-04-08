import sys
import os

# Fix for Windows terminal emojis
if sys.stdout.encoding != 'utf-8':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8', errors='replace')
    except Exception:
        pass

from dotenv import load_dotenv

from agents.message_bus import init_message_bus, print_full_message_log
from agents.ceo_agent import CEOAgent
from agents.ui_utils import print_banner, print_final_summary, console, show_spinner

# Load environment variables here (GITHUB_TOKEN, SLACK_BOT_TOKEN)
load_dotenv()

def main():
    print_banner()

    # Initialize the SQLite message bus database
    init_message_bus()

    # The startup idea to feed the CEO
    from rich.prompt import Prompt
    
    startup_idea = Prompt.ask(
        "[bold cyan]Enter your Startup Idea[/bold cyan]", 
        default="ZetaMize AI Sales OS - Automated B2B lead generation and personalized outreach"
    )

    # Initialize and run the Orchestrator
    ceo = CEOAgent()
    try:
        final_results = ceo.run(startup_idea)
        
        # Show final message log for evaluation
        print_full_message_log()
        
        # Final Success Table
        print_final_summary(final_results)
        
    except Exception as e:
        console.print(f"\n[bold red]❌ FATAL SYSTEM ERROR:[/bold red] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
