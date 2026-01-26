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
    console.print(f"[bold red]{error}[/bold red]")

def print_warning(warning):
    console.print(f"[bold yellow]{warning}[/bold yellow]")

def print_text(text, tab = False):
    if tab:
        console.print(tabulate.tabulate(text, headers="keys", tablefmt="fancy_grid"))
    else:
        try:
            console.print(json.dumps(text, indent=4, sort_keys=True))
        except:
            console.print(text)