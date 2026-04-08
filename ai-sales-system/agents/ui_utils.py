import time
import sys
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.spinner import Spinner
from rich.table import Table
from rich.box import ROUNDED

console = Console()

AGENT_COLORS = {
    "ceo": "bold cyan",
    "product": "bold magenta",
    "engineer": "bold green",
    "marketing": "bold yellow",
    "qa": "bold red",
    "system": "bold white"
}

def print_banner():
    """Prints the main LaunchMind banner."""
    console.print("\n")
    console.print(Panel(
        Text("🚀 LAUNCHMIND MAS: Autonomous AI Startup Team", justify="center", style="bold white on blue"),
        box=ROUNDED,
        padding=(1, 2)
    ))
    console.print("\n")

def print_step(agent, activity):
    """Prints a step with a spinner."""
    color = AGENT_COLORS.get(agent.lower(), "white")
    console.print(f"[{color}]●[/{color}] [bold white]{agent.upper()}:[/bold white] {activity}...", end="\r")

def print_message(from_agent, to_agent, msg_type, payload):
    """Prints a message in a beautiful panel."""
    from_color = AGENT_COLORS.get(from_agent.lower(), "white")
    to_color = AGENT_COLORS.get(to_agent.lower(), "white")
    
    header = Text()
    header.append(from_agent.upper(), style=from_color)
    header.append(" ➔ ", style="bold white")
    header.append(to_agent.upper(), style=to_color)
    header.append(f" [{msg_type.upper()}]", style="dim white")

    # Format payload nicely
    import json
    content = json.dumps(payload, indent=2)
    
    console.print("\n")
    console.print(Panel(
        content,
        title=header,
        title_align="left",
        border_style=from_color,
        box=ROUNDED,
        padding=(1, 2)
    ))

def print_agent_thought(agent, thought):
    """Prints an agent's internal reasoning/thought process."""
    color = AGENT_COLORS.get(agent.lower(), "white")
    console.print(f"\n[italic {color}]🗨️ {agent.upper()} Reasoning: {thought}[/italic {color}]")

def typing_print(text, style="white", speed=0.005):
    """Prints text with a typing effect."""
    for char in text:
        console.print(char, style=style, end="")
        sys.stdout.flush()
        time.sleep(speed)
    console.print()

def print_status_update(message, style="green"):
    """Prints a success or status update."""
    console.print(f"\n[bold {style}]✨ {message}[/bold {style}]")

def show_spinner(text, duration=2):
    """Shows a spinner for a certain duration."""
    with console.status(f"[bold yellow]{text}...", spinner="dots"):
        time.sleep(duration)

def print_final_summary(results):
    """Prints the final execution summary table."""
    table = Table(title="🚀 Final Startup Launch Summary", box=ROUNDED, header_style="bold blue")
    table.add_column("Agent", style="cyan")
    table.add_column("Output / Result", style="white")

    table.add_row("Product", "Value Prop: " + results.get('product_spec', {}).get('value_proposition', 'N/A'))
    table.add_row("Engineer", f"GitHub PR Created: [link={results.get('engineer_result', {}).get('pr_url')}]View PR[/link]")
    table.add_row("Marketing", "Email Sent & Slack Notification Posted")
    table.add_row("QA", f"Verdict: {results.get('qa_result', {}).get('verdict', 'N/A').upper()}")

    console.print("\n")
    console.print(table)
    console.print("\n[bold green]✅ MISSION ACCOMPLISHED! Startup build successful.[/bold green]\n")
