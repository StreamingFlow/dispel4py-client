from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Middle, Vertical
from textual.widgets import Button, Input, Label, Static


class LoginApp(App):
    """A small modal-style login form that authenticates against the d4p client.

    Returns (via App.run()):
        True  -> authenticated successfully
        False -> user cancelled (Esc / Ctrl+Q)
    """

    CSS = """
    Screen {
        align: center middle;
    }

    #card {
        width: 54;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $panel;
    }

    #title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #subtitle {
        width: 100%;
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    Input {
        margin-bottom: 1;
    }

    #login {
        width: 100%;
        margin-top: 1;
    }

    #status {
        width: 100%;
        text-align: center;
        height: 1;
        margin-top: 1;
    }

    .error { color: $error; }
    .info  { color: $text-muted; }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("ctrl+q", "cancel", "Quit", show=False),
    ]

    def __init__(self, client):
        super().__init__()
        self.client = client
        self._busy = False

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                with Vertical(id="card"):
                    yield Label("Laminar", id="title")
                    yield Label("Sign in to continue", id="subtitle")
                    yield Input(placeholder="Username", id="username")
                    yield Input(placeholder="Password", password=True, id="password")
                    yield Button("Log in", variant="primary", id="login")
                    yield Static("", id="status")

    def on_mount(self) -> None:
        self.query_one("#username", Input).focus()

    @on(Input.Submitted, "#username")
    def _username_to_password(self) -> None:
        self.query_one("#password", Input).focus()

    @on(Input.Submitted, "#password")
    @on(Button.Pressed, "#login")
    def _submit(self) -> None:
        if self._busy:
            return

        username = self.query_one("#username", Input).value.strip()
        password = self.query_one("#password", Input).value

        if not username or not password:
            self._set_status("Enter both username and password.", error=True)
            return

        self._set_busy(True)
        self._set_status("Authenticating\u2026", error=False)
        self._authenticate(username, password)

    def action_cancel(self) -> None:
        self.exit(False)

    @work(thread=True, exclusive=True)
    def _authenticate(self, username: str, password: str) -> None:
        try:
            self.client.login(username, password)
            ok = self.client.get_login() is not None
        except Exception as exc:  # noqa: BLE001 - surface any client error to the user
            self.call_from_thread(self._on_failure, f"Login error: {exc}")
            return

        if ok:
            self.call_from_thread(self.exit, True)
        else:
            self.call_from_thread(self._on_failure, "Invalid login. Try again.")

    def _on_failure(self, message: str) -> None:
        self._set_busy(False)
        self._set_status(message, error=True)
        pw = self.query_one("#password", Input)
        pw.value = ""
        pw.focus()

    def _set_status(self, message: str, *, error: bool) -> None:
        status = self.query_one("#status", Static)
        status.remove_class("error", "info")
        status.add_class("error" if error else "info")
        status.update(message)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.query_one("#username", Input).disabled = busy
        self.query_one("#password", Input).disabled = busy
        self.query_one("#login", Button).disabled = busy


def run_login(client) -> bool:
    return bool(LoginApp(client).run())