from __future__ import annotations

from typing import Any, Optional, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import DataTable, Footer, Header, Input, Static

# Field order for the detail view: (label, dict-key).
_FIELDS: Sequence[tuple[str, str]] = (
    ("ID", "ID"),
    ("LLM", "LLM provider / model"),
    ("Description", "Description"),
    ("Inputs", "Inputs"),
    ("Outputs", "Outputs"),
    ("Tags", "Tags"),
    ("Imports", "Imports"),  # PE only; skipped automatically when absent
)

_TYPE_COLOR = {"PE": "green", "WF": "magenta"}


def _fmt(value: Any) -> str:
    """Format a field value (str / list / tuple / dict / None) for display."""
    if value is None:
        return "[dim]—[/dim]"
    if isinstance(value, dict):
        return "\n".join(f"[cyan]{k}[/cyan]: {v}" for k, v in value.items()) or "[dim]—[/dim]"
    if isinstance(value, (list, tuple)):
        return "\n".join(f"• {item}" for item in value) or "[dim]—[/dim]"
    return str(value).strip() or "[dim]—[/dim]"


def _object_panel(obj: dict[str, Any]) -> Panel:
    """A bordered, color-coded detail panel for one object."""
    obj_type = str(obj.get("Type", "?"))
    color = _TYPE_COLOR.get(obj_type, "white")

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold yellow", justify="right", no_wrap=True)
    grid.add_column(overflow="fold")
    for label, key in _FIELDS:
        if key in obj:
            grid.add_row(label, _fmt(obj.get(key)))

    return Panel(
        grid,
        title=f"[bold]{obj.get('Name', '<unnamed>')}[/bold]  [{color}]{obj_type}[/{color}]",
        title_align="left",
        border_style=color,
        padding=(1, 2),
    )


def _matches(obj: dict[str, Any], query: str) -> bool:
    """Case-insensitive substring match across Type / Name / ID / Tags."""
    if not query:
        return True
    q = query.lower()
    haystack = " ".join(str(obj.get(k, "")) for k in ("Type", "Name", "ID"))
    tags = obj.get("Tags") or []
    if isinstance(tags, (list, tuple)):
        haystack += " " + " ".join(str(t) for t in tags)
    return q in haystack.lower()


class _RegistryBrowser(App):

    CSS = """
    #search { dock: top; }
    Horizontal { height: 1fr; }
    DataTable { width: 45%; border-right: solid $accent; }
    #detail-pane { width: 55%; }
    #detail { padding: 1 2; }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("/", "focus_search", "Search"),
        ("escape", "clear_search", "Clear search"),
    ]

    def __init__(self, objects: Sequence[dict[str, Any]], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.objects = list(objects)
        self.filtered: list[dict[str, Any]] = list(self.objects)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Input(placeholder="Search type / name / id / tags…", id="search")
        with Horizontal():
            yield DataTable(id="list", cursor_type="row", zebra_stripes=True)
            with VerticalScroll(id="detail-pane"):
                yield Static(id="detail")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Registry"
        self.sub_title = f"{len(self.objects)} object(s)"
        self.query_one(DataTable).add_columns("Type", "Name", "ID")
        self._populate()

    def _populate(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for idx, obj in enumerate(self.filtered):
            table.add_row(
                str(obj.get("Type", "?")),
                str(obj.get("Name", "")),
                str(obj.get("ID", "")),
                key=str(idx),
            )
        detail = self.query_one("#detail", Static)
        if self.filtered:
            self._show(0)
        else:
            detail.update("[dim]No matching objects.[/dim]")

    def _show(self, idx: int) -> None:
        self.query_one("#detail", Static).update(_object_panel(self.filtered[idx]))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None and event.row_key.value is not None:
            self._show(int(event.row_key.value))

    def on_input_changed(self, event: Input.Changed) -> None:
        self.filtered = [o for o in self.objects if _matches(o, event.value)]
        self.sub_title = f"{len(self.filtered)} / {len(self.objects)} object(s)"
        self._populate()

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_clear_search(self) -> None:
        self.query_one("#search", Input).value = ""
        self.query_one(DataTable).focus()


class ListCommand:

    def __init__(self, client: Any, console: Optional[Console] = None) -> None:
        self.client = client
        self.console = console or Console()

    # --- public API -------------------------------------------------------
    def help(self) -> None:
        """Print usage information and keybindings for the list command."""
        body = Table.grid(padding=(0, 2))
        body.add_column(style="bold yellow", justify="right", no_wrap=True)
        body.add_column()
        body.add_row("↑ / ↓ / click", "move through the list; detail shows on the right")
        body.add_row("/", "focus the search box")
        body.add_row("type", "filter by type / name / id / tags")
        body.add_row("Esc", "clear the search")
        body.add_row("q", "quit the browser")

        self.console.print(
            Panel(
                body,
                title="[bold]list[/bold]  —  browse the object registry",
                title_align="left",
                subtitle="[dim]PE (green) and WF (magenta) objects[/dim]",
                subtitle_align="left",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def list(self) -> None:
        """Fetch the registry and open the interactive browser."""
        try:
            description, _registry = self.client.get_Registry()
        except Exception as e:  # mirror your existing print_error flow
            self.console.print(f"[red]An error occurred:[/red] {e}")
            return

        if not description:
            self.console.print("[dim]No objects in the registry.[/dim]")
            return

        self._build_app(description).run()

    # --- internal ---------------------------------------------------------
    def _build_app(self, objects: Sequence[dict[str, Any]]) -> _RegistryBrowser:
        """Build (but don't run) the browser app — handy for testing."""
        return _RegistryBrowser(objects)

