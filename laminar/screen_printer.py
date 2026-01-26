import json
import os

import tabulate
from rich import pretty, print
from rich.console import Console

console = Console()


pretty.install()

def clear_terminal():
    if os.name == "nt":
        os.system('cls')
    else:
        os.system('clear')

def print_status(status):
    console.print(f"[bold green]{status}[/bold green]")

def print_error(error):
    console.print(f"[bold red]ERR: {error}[/bold red]")

def print_warning(warning):
    console.print(f"[bold yellow]{warning}[/bold yellow]")


def print_text(text, tab=False):
    """
    Prints text, dict/list, or JSON string in a pretty way.

    Args:
        text: str, dict, list, or JSON string
        tab: if True, prints as table (expects list of dicts)
    """
    if tab:
        console.print(tabulate.tabulate(text, headers="keys", tablefmt="fancy_grid"))
        return

    # If it's a string, try parsing as JSON
    if isinstance(text, str):
        try:
            parsed = json.loads(text)
            console.print_json(data=parsed)
        except json.JSONDecodeError:
            # Not JSON, print as plain string
            console.print(f"[bold green]{text}[/bold green]")
    elif isinstance(text, (dict, list)):
        console.print_json(data=text)
    else:
        console.print(text)