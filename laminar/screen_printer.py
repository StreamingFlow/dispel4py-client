import json
import os
import traceback
import tabulate
from rich import pretty, print
from rich.console import Console
from rich.syntax import Syntax
import shutil
import textwrap
from tabulate import tabulate

console = Console()

pretty.install()

term_width = shutil.get_terminal_size().columns


def wrap_cell(cell, width):
    return "\n".join(textwrap.wrap(str(cell), width=width))


def wrap_table(rows, headers):
    # crude column width guess
    col_width = max(10, term_width // len(headers) - 3)

    wrapped = []
    for row in rows:
        wrapped.append({
            k: wrap_cell(v, col_width)
            for k, v in row.items()
        })
    return wrapped


def clear_terminal():
    if os.name == "nt":
        os.system('cls')
    else:
        os.system('clear')


def print_status(status):
    console.print(f"[bold green]{status}[/bold green]")


def print_error(error, _traceback=True):
    if _traceback:
        console.print(f"{traceback.format_exc()}")
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
        wrapped_text = wrap_table(text, headers=text[0].keys())
        console.print(tabulate(wrapped_text, headers="keys", tablefmt="fancy_grid"))
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


def print_code(code):
    console.print(Syntax(code, "python"))
