from __future__ import annotations

import argparse
import importlib.util
import shlex
import sys
from typing import Optional

from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, RichLog

from laminar import screen_printer
from laminar.argument_parser import CustomArgumentParser, type_checker
from laminar.client.d4pyclient import d4pClient
from laminar.clitools.advanced_search import AdvancedSearchCommand
from laminar.clitools.list import ListCommand
from laminar.clitools.register import RegisterCommand
from laminar.clitools.remove import RemoveCommand
from laminar.clitools.run import RunCommand
from laminar.clitools.search import SearchCommand
from laminar.clitools.update_description import UpdateDescriptionCommand
from laminar.llms.LLMConnector import LLMConnector
from laminar.screen_printer import print_error, print_text, print_warning

_TRANSCRIPT_CAP = 1000

_BANNER = """\
\033[36m
  _                    _                             ____ _     ___
 | |    __ _ _ __ ___ (_)_ __   __ _ _ __           / ___| |   |_ _|
 | |   / _` | '_ ` _ \\| | '_ \\ / _` | '__|  _____  | |   | |    | |
 | |__| (_| | | | | | | | | | | (_| | |    |_____| | |___| |___ | |
 |_____\\__,_|_| |_| |_|_|_| |_|\\__,_|_|             \\____|_____|___|
\033[0m\033[1m            Welcome to the Laminar CLI!\033[0m"""

# command -> "inline" (run in-shell) or "handoff" (exit shell, run at top level)
_KIND = {
    "help": "inline",
    "search": "inline",
    "code_recommendation": "inline",
    "run": "inline",
    "register": "inline",
    "describe": "inline",
    "update_description": "inline",
    "list": "handoff",
    "advanced_search": "handoff",
    "remove": "inline",
}

_INLINE_BLURB = {
    "describe": "describe <identifier> [--source_code|-sc]   Show details for a PE or workflow.",
    "code_recommendation": "code_recommendation <workflow|pe> <snippet> [--embedding_type llm|spt]",
    "help": "help [command]   List commands, or show help for one.",
    "quit": "quit | exit   Leave the shell.",
}


class ShellSession:
    """State that survives the shell being torn down and relaunched."""

    def __init__(self, client: d4pClient) -> None:
        self.client = client
        self.loaded_modules: dict = {}
        self.transcript: list[str] = []  # ANSI lines, replayed on relaunch
        self.history: list[str] = []  # command history
        self.initialized = False
        # command objects (built once, on first launch)
        self.llmConnector: Optional[LLMConnector] = None
        self.search_command: Optional[SearchCommand] = None
        self.register_command: Optional[RegisterCommand] = None
        self.remove_command: Optional[RemoveCommand] = None
        self.run_command: Optional[RunCommand] = None
        self.update_description_command: Optional[UpdateDescriptionCommand] = None
        self.list_command: Optional[ListCommand] = None
        self.advanced_search_command: Optional[AdvancedSearchCommand] = None

    def note(self, ansi_line: str) -> None:
        self.transcript.append(ansi_line)
        if len(self.transcript) > _TRANSCRIPT_CAP:
            del self.transcript[:-_TRANSCRIPT_CAP]

    def init_commands(self, status_cb=None) -> None:
        from laminar.llms.model_manager import ensure_models_available
        ensure_models_available(status_cb=status_cb)

        self.llmConnector = LLMConnector()
        encoder = self.client._get_encoder(ensure_models=False)
        self.list_command = ListCommand(client=self.client)
        self.search_command = SearchCommand(client=self.client)
        self.register_command = RegisterCommand(
            client=self.client, llmConnector=self.llmConnector,
            loaded_modules=self.loaded_modules)
        self.remove_command = RemoveCommand(client=self.client)
        self.run_command = RunCommand(client=self.client)
        self.update_description_command = UpdateDescriptionCommand(client=self.client)
        self.advanced_search_command = AdvancedSearchCommand(
            client=self.client, encoder=encoder, llm_connector=self.llmConnector)
        self._load_modules_on_startup()
        self.initialized = True

    def _load_modules_on_startup(self) -> None:
        for workflow in self.client.get_Workflows():
            src = workflow["moduleSourceCode"]
            if not src:
                continue
            module_name = workflow["moduleName"] or "tmp"
            spec = importlib.util.spec_from_loader(module_name, loader=None)
            mod = importlib.util.module_from_spec(spec)
            try:
                exec(src, mod.__dict__)
                sys.modules[module_name] = mod
                self.loaded_modules[module_name] = mod
            except Exception as exc:  # noqa: BLE001
                self.note(f"\033[33m[load] {exc}\033[0m")


class _ConsoleRelay:
    """File-like sink that streams a worker's stdout / Rich output into the
    transcript ``RichLog`` on the UI thread, one line at a time, with colour."""

    def __init__(self, app: "LaminarShell") -> None:
        self._app = app
        self._buf = ""

    def write(self, s: str) -> int:
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._app.call_from_thread(self._app.write_line, line)
        return len(s)

    def flush(self) -> None:
        if self._buf:
            self._app.call_from_thread(self._app.write_line, self._buf)
            self._buf = ""


class LaminarShell(App):
    """Top-level Laminar shell: a scrolling transcript plus a command line.

    ``run()`` returns one of:
        None                         -> user quit
        ("run", name, rest)          -> outer loop should run a handoff tool
    """

    CSS = """
    #output {
        height: 1fr;
        border: round $accent;
        padding: 0 1;
        background: $panel;
    }
    #command { dock: bottom; }
    #command:disabled { opacity: 0.6; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+l", "clear", "Clear"),
    ]

    def __init__(self, session: ShellSession) -> None:
        super().__init__()
        self.session = session
        self._console_width = 100
        self._hist_idx = 0

    # -- layout --------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield RichLog(id="output", markup=False, highlight=False, wrap=True)
            yield Input(placeholder="Loading\u2026", id="command", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Laminar CLI"
        self.sub_title = f"Logged in as {self.session.client.get_login()}"
        self._console_width = max(40, self.size.width - 6)
        self._hist_idx = len(self.session.history)

        log = self.query_one(RichLog)
        if self.session.transcript:
            for line in self.session.transcript:  # replay (no re-append)
                log.write(Text.from_ansi(line))
        else:
            self.write_line(_BANNER)
            log.write("")

        if self.session.initialized:
            self._finish_startup(ok=True, announce=False)
        else:
            self._startup()

    def on_resize(self) -> None:
        self._console_width = max(40, self.size.width - 6)

    @work(thread=True, exclusive=True)
    def _startup(self) -> None:
        def status(msg: str) -> None:
            self.call_from_thread(self.write_line, msg)

        status("Loading modules from registry\u2026")
        ok = True
        try:
            self.session.init_commands(status_cb=status)
        except Exception as exc:  # noqa: BLE001
            ok = False
            self.call_from_thread(self.write_line, f"\033[31m[startup] {exc}\033[0m")
        self.call_from_thread(self._finish_startup, ok, True)

    def _finish_startup(self, ok: bool = True, announce: bool = False) -> None:
        cmd = self.query_one("#command", Input)
        if not (ok and self.session.initialized):
            cmd.placeholder = "Startup failed \u2014 commands disabled"
            cmd.disabled = True
            self.write_line(
                "\033[31mStartup did not complete: the required encoder models are not "
                "available, so commands are disabled. Check your network "
                "connection and restart Laminar.\033[0m")
            return
        cmd.placeholder = "Type a command \u2014 try `help`"
        cmd.disabled = False
        cmd.focus()
        if announce:
            self.write_line("Ready. Type `help` to list commands.")

    # -- transcript helpers (UI thread) -------------------------------------

    def _emit(self, line: str) -> None:
        self.query_one(RichLog).write(Text.from_ansi(line))

    def write_line(self, line: str) -> None:
        for part in line.split("\n"):
            self.session.note(part)
            self._emit(part)

    # -- command line --------------------------------------------------------

    @on(Input.Submitted, "#command")
    def _on_submit(self, event: Input.Submitted) -> None:
        line = event.value.strip()
        self.query_one("#command", Input).value = ""
        if not line:
            return
        self.session.history.append(line)
        self._hist_idx = len(self.session.history)
        self.write_line(f"\033[1;36m(laminar) >\033[0m {line}")

        name, _, rest = line.partition(" ")
        name = name.lower()
        rest = rest.strip()

        if name in ("quit", "exit"):
            self.exit(None)
            return

        kind = _KIND.get(name)
        if kind is None:
            self.write_line(f"\033[33mUnknown command: {name}. Try `help`.\033[0m")
            return

        if kind == "handoff":
            # leave the shell cleanly; the outer loop runs the tool, then relaunches.
            self.write_line(f"\033[2m(launching {name}\u2026)\033[0m")
            self.exit(("run", name, rest))
        else:
            self._set_busy(True)
            self._run_inline(name, rest)

    def on_key(self, event) -> None:
        if not isinstance(self.focused, Input) or not self.session.history:
            return
        if event.key == "up":
            self._hist_idx = max(0, self._hist_idx - 1)
        elif event.key == "down":
            self._hist_idx = min(len(self.session.history), self._hist_idx + 1)
        else:
            return
        event.prevent_default()
        box = self.query_one("#command", Input)
        hist = self.session.history
        box.value = hist[self._hist_idx] if self._hist_idx < len(hist) else ""

    # -- inline execution (worker thread, output captured) ------------------

    @work(thread=True, exclusive=True)
    def _run_inline(self, name: str, rest: str) -> None:
        relay = _ConsoleRelay(self)
        capture = screen_printer.Console(
            file=relay, force_terminal=True, color_system="truecolor",
            width=self._console_width, soft_wrap=False)
        saved_console = screen_printer.console
        saved_stdout = sys.stdout
        screen_printer.console = capture
        sys.stdout = relay
        try:
            self._inline_dispatch(name, rest)
        except SystemExit:
            pass  # CustomArgumentParser may try to exit; swallow inside the shell
        except Exception as exc:  # noqa: BLE001
            print_error(f"An error occurred: {exc}")
        finally:
            relay.flush()
            screen_printer.console = saved_console
            sys.stdout = saved_stdout
            self.call_from_thread(self._set_busy, False)

    def _inline_dispatch(self, name: str, rest: str) -> None:
        s = self.session
        if name == "search":
            s.search_command.search(rest)
        elif name == "run":
            s.run_command.run(rest)
        elif name == "register":
            s.register_command.register(rest)
        elif name == "update_description":
            s.update_description_command.update_description(rest)
        elif name == "describe":
            self._cmd_describe(rest)
        elif name == "code_recommendation":
            self._cmd_code_recommendation(rest)
        elif name == "remove":
            s.remove_command.remove(rest)
        elif name == "help":
            self._cmd_help(rest)

    # -- ported inline handlers (were do_* on the old CLI) ------------------

    def _cmd_describe(self, arg: str) -> None:
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("identifier", type=type_checker)
        parser.add_argument("--source_code", "-sc", action="store_true",
                            help="Include the source code in the description")
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            data = (self.session.client.get_PE(args["identifier"])
                    or self.session.client.get_Workflow(args["identifier"]))
            if data:
                obj, sc = data[0], data[1]
                print_text([{"description": data[4]}], tab=True)
                self.session.client.describe(obj, sc, include_source_code=args["source_code"])
            else:
                print_warning(f"No description found for '{args['identifier']}'")
        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "describe"))

    def _cmd_code_recommendation(self, arg: str) -> None:
        parser = CustomArgumentParser(exit_on_error=False)
        parser.add_argument("search_type", choices=["workflow", "pe"], default="pe")
        parser.add_argument("code_snippet")
        parser.add_argument("--embedding_type", choices=["llm", "spt"], default="spt")
        try:
            args = vars(parser.parse_args(shlex.split(arg)))
            feedback = self.session.client.code_Recommendation(
                args["code_snippet"], args["search_type"], args["embedding_type"])
            print_text(feedback)
        except argparse.ArgumentError as e:
            print_error(e.message.replace("laminar.py", "code_recommendation"))

    def _cmd_help(self, arg: str) -> None:
        arg = arg.strip()
        if arg:
            s = self.session
            obj = {
                "search": s.search_command, "run": s.run_command,
                "register": s.register_command, "remove": s.remove_command,
                "update_description": s.update_description_command,
                "list": s.list_command, "advanced_search": s.advanced_search_command,
            }.get(arg)
            if obj is not None and hasattr(obj, "help"):
                obj.help()
            elif arg in _INLINE_BLURB:
                print_text(_INLINE_BLURB[arg])
            else:
                print_warning(f"No help for '{arg}'.")
            return

        table = Table(title="Laminar commands", title_justify="left", header_style="bold cyan")
        table.add_column("Command", style="bold yellow", no_wrap=True)
        table.add_column("Where")
        table.add_column("What it does")
        for row in [
            ("search", "in-shell", "Literal / semantic registry search"),
            ("code_recommendation", "in-shell", "Find similar code in the registry"),
            ("run", "in-shell", "Execute a registered workflow"),
            ("register", "in-shell", "Register a workflow / PE / directory"),
            ("describe", "in-shell", "Show details of a PE or workflow"),
            ("update_description", "in-shell", "Edit a stored description"),
            ("list", "full screen", "Interactive registry browser (Textual)"),
            ("advanced_search", "full screen", "LLM-assisted search (Textual)"),
            ("remove", "full screen", "Remove an object (asks to confirm)"),
            ("help", "in-shell", "This help; `help <command>` for detail"),
            ("quit / exit", "-", "Leave the shell"),
        ]:
            table.add_row(*row)
        screen_printer.console.print(table)

    # -- actions -------------------------------------------------------------

    def action_clear(self) -> None:
        self.session.transcript.clear()
        self.query_one(RichLog).clear()

    def _set_busy(self, busy: bool) -> None:
        box = self.query_one("#command", Input)
        box.disabled = busy
        if not busy:
            box.focus()


def _run_handoff_tool(session: ShellSession, name: str, rest: str) -> None:
    """Run a full-screen / interactive tool at the top level (no app nesting)."""
    try:
        if name == "list":
            session.list_command.list()
        elif name == "advanced_search":
            session.advanced_search_command.search_library(rest)
        elif name == "remove":
            session.remove_command.remove(rest)
            input("\nPress Enter to return to the shell\u2026")
    except KeyboardInterrupt:
        pass
    except Exception as exc:  # noqa: BLE001
        print_error(f"An error occurred while running '{name}': {exc}")
        try:
            input("\nPress Enter to return to the shell\u2026")
        except EOFError:
            pass
    session.note(f"\033[2m(returned from {name})\033[0m")
