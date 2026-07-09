import json
import queue
import traceback

import numpy as np
from rich.pretty import Pretty
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Footer, Header, RichLog, Static, TextArea

from laminar.client.d4pyclient import d4pClient
from laminar.clitools.register import RegisterCommand
from laminar.llms.LLMConnector import LLMConnector
from laminar.llms.encoder import LaminarCodeEncoder
from laminar.llms.prompts import refine_prompt
from laminar.screen_printer import (
    print_code as _orig_print_code,
    print_warning as _orig_print_warning,
    print_status as _orig_print_status,
)
from laminar.screen_printer import print_text as _orig_print_text, print_error as _orig_print_error

_ACTIVE_SINK = None  # set to the running SearchTUI during a session


def print_text(*args, **kwargs):
    sink = _ACTIVE_SINK
    if sink is not None:
        sink.sink_text(*args, **kwargs)
    else:
        _orig_print_text(*args, **kwargs)


def print_error(*args, **kwargs):
    sink = _ACTIVE_SINK
    if sink is not None:
        sink.sink_error(*args, **kwargs)
    else:
        _orig_print_error(*args, **kwargs)


def print_status(*args, **kwargs):
    sink = _ACTIVE_SINK
    if sink is not None:
        sink.sink_status(*args, **kwargs)
    else:
        _orig_print_status(*args, **kwargs)


def print_warning(*args, **kwargs):
    sink = _ACTIVE_SINK
    if sink is not None:
        sink.sink_warning(*args, **kwargs)
    else:
        _orig_print_warning(*args, **kwargs)


def print_code(code=None, *args, **kwargs):
    sink = _ACTIVE_SINK
    if sink is not None:
        sink.sink_code(code)
    else:
        _orig_print_code(code, *args, **kwargs)


_builtin_input = input  # capture before shadowing the module-level name


def input(prompt=""):  # noqa: A001 - intentionally shadows builtin in this module
    sink = _ACTIVE_SINK
    if sink is not None:
        return sink.sink_ask(str(prompt))
    return _builtin_input(prompt)


_SHUTDOWN = object()  # pushed into the answer queue to unblock input() on quit


def _fmt_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}={v}" for k, v in value.items())
    return str(value)


def _rows_to_table(rows) -> Table:
    if isinstance(rows, dict):
        rows = [rows]
    columns = []
    for row in rows:  # union of keys, first-seen order
        for key in row.keys():
            if key not in columns:
                columns.append(key)
    table = Table(show_header=True, header_style="bold magenta",
                  expand=True, show_lines=True)
    for col in columns:
        table.add_column(str(col), overflow="fold")  # long text wraps, not overflows
    for row in rows:
        table.add_row(*(_fmt_cell(row.get(col)) for col in columns))
    return table


def _is_table_like(value) -> bool:
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list) and value:
        return all(isinstance(item, dict) for item in value)
    return False


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None or a.size == 0 or b.size == 0:
        return -1.0
    # embeddings already normalized in CELL 3
    return float(np.dot(a, b))


def hybrid_weights(input_type: str):
    # return (desc_weight, code_weight)
    if input_type == "mixed":
        return 0.5, 0.5
    if input_type == "code":
        return 0.2, 0.8
    return 1.0, 0.0


def tag_boost(query: str, tags_json: str, max_boost: float = 0.06) -> float:
    if not tags_json:
        return 0.0

    if not isinstance(tags_json, list):
        try:
            tags = set(json.loads(tags_json))
        except Exception as e:
            print_error(f"WARNING: failed to parse tags: {e}")
            return 0.0
    else:
        tags = set(tags_json)

    q = (query or "").lower()
    hits = 0
    for t in tags:
        t2 = str(t).lower().replace("_", " ")
        if t2 and t2 in q:
            hits += 1

    return min(max_boost, 0.02 * hits)


def _safe_json_loads(s: str, default):
    if isinstance(s, list):
        return s

    try:
        return json.loads(s) if s else default
    except Exception as e:
        print_error(f"WARNING: failed to load JSON: {e}")
        print_text(f"Input: {s}")
        return default


class AdvancedSearchCommand:

    def __init__(self, client: d4pClient, encoder: LaminarCodeEncoder = None, llm_connector: LLMConnector = None,
                 registerInterface: RegisterCommand = None):
        self.client = client
        self.encoder = encoder or LaminarCodeEncoder()
        self.connector = llm_connector or LLMConnector()
        self.registerInterface = registerInterface or RegisterCommand(self.client, llmConnector=self.connector)

        self._CAP_HINTS = {
            "csv": ["csv", "readcsv"],
            "filter": ["filter", "filtering", "threshold", "quality"],
            "fft": ["fft", "frequency", "spectrum"],
            "window": ["window", "hann", "hamming"],
            "bandpass": ["bandpass", "signal processing"],
            "detrend": ["detrend", "signal processing"],
            "write": ["write", "jsonl", "export", "output"]
        }

    def _workflow_structure_score(self, query: str, pe_list_json: str, pe_tags_by_name: dict) -> float:
        def _extract_requested_caps(q: str) -> set:
            q = (q or "").lower()
            request = set()

            for k in self._CAP_HINTS.keys():
                if k in q:
                    request.add(k)
            if "cross" in q and "correlation" in q:
                request.add("cross_correlation")
            return request

        req = _extract_requested_caps(query)
        if not req:
            return 0.0
        pe_list = _safe_json_loads(pe_list_json, [])
        if not pe_list:
            return 0.0

        tags_union = set()
        for pe_name in pe_list:
            tags_union |= set(pe_tags_by_name.get(pe_name, []))

        matched = 0
        for cap in req:
            if cap == "cross_correlation":
                if ("correlation" in tags_union) or ("signal processing" in tags_union):
                    matched += 1
                continue
            hints = self._CAP_HINTS.get(cap, [])
            if any(h in tags_union for h in hints):
                matched += 1

        return matched / max(1, len(req))

    def _retrieve(self,
                  query: str,
                  *,
                  kind: str,
                  input_type: str,
                  top_n: int = 30):
        w_desc, w_code = hybrid_weights(input_type)
        q_text, q_code = self.encoder.embed_query(query, input_type)
        lex = self.client.lexicalScores(kind, query, limit=120)

        # tags for structure
        pe_tags_by_name = {}

        registry, _ = self.client.getRegistry(extended=True)

        pe_rows = [itm for itm in registry if itm["Type"] == "PE"]
        wf_rows = [itm for itm in registry if itm["Type"] == "WF"]

        for pe in pe_rows:
            name = pe["peName"]
            pe_tags_by_name[name] = pe['tags'] if isinstance(pe['tags'], list) else []

        # weights
        W_EMB = 0.60
        W_LEX = 0.25
        W_TAG = 0.10
        W_STR = 0.05

        candidates = []

        if kind in ("pe", "either"):

            for pe in pe_rows:

                pe_id = pe["peId"]
                name = pe["peName"]
                code = pe["peCode"]
                desc = pe["description"]
                tags_json = pe["tags"]

                s_desc = cosine(q_text, self.encoder.embed_text(desc)) if (
                        q_text is not None and desc is not None) else -1.0
                s_code = cosine(q_code, self.encoder.embed_code(code)) if (
                        q_code is not None and code is not None) else -1.0

                emb = 0.0
                wsum = 0.0
                if w_desc > 0 and s_desc >= 0:
                    emb += w_desc * s_desc
                    wsum += w_desc
                if w_code > 0 and s_code >= 0:
                    emb += w_code * s_code
                    wsum += w_code
                emb = emb / wsum if wsum > 0 else max(s_desc, s_code)

                lex_s = lex.get(("pe", int(pe_id)), 0.0)
                tag_s = tag_boost(query, tags_json) / 0.06  # ~0..1

                final = W_EMB * emb + W_LEX * lex_s + W_TAG * tag_s

                candidates.append({
                    "type": "pe", "id": int(pe_id), "name": name,
                    "score": float(final),
                    "emb": float(emb), "lex": float(lex_s), "tag": float(tag_s), "struct": 0.0,
                    "sim_desc": float(s_desc), "sim_code": float(s_code),
                    "description": desc, "code": code,
                    "tags_json": tags_json
                })

        if kind in ("workflow", "either"):
            for workflow in wf_rows:
                wid = workflow["workflowId"]
                name = workflow["workflowName"]
                code = workflow["workflowCode"]
                desc = workflow["description"]
                dblob = workflow["descEmbedding"]
                tags_json = workflow["tags"]
                pe_list_json = workflow["tags"]
                edges_json = None

                s_desc = cosine(q_text, self.encoder.embed_text(desc)) if (
                        q_text is not None and dblob is not None) else -1.0
                s_code = cosine(q_code, self.encoder.embed_code(code)) if (
                        q_code is not None and code is not None) else -1.0

                emb = 0.0
                wsum = 0.0
                if w_desc > 0 and s_desc >= 0:
                    emb += w_desc * s_desc
                    wsum += w_desc
                if w_code > 0 and s_code >= 0:
                    emb += w_code * s_code
                    wsum += w_code
                emb = emb / wsum if wsum > 0 else max(s_desc, s_code)

                lex_s = lex.get(("workflow", int(wid)), 0.0)
                tag_s = tag_boost(query, tags_json) / 0.06
                struct_s = self._workflow_structure_score(query, pe_list_json, pe_tags_by_name)

                final = W_EMB * emb + W_LEX * lex_s + W_TAG * tag_s + W_STR * struct_s

                candidates.append({
                    "type": "workflow", "id": int(wid), "name": name,
                    "score": float(final),
                    "emb": float(emb), "lex": float(lex_s), "tag": float(tag_s), "struct": float(struct_s),
                    "sim_desc": float(s_desc), "sim_code": float(s_code),
                    "description": desc, "code": code,
                    "tags_json": tags_json, "pe_list_json": pe_list_json, "edges_json": edges_json
                })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:top_n], {"w_desc": w_desc, "w_code": w_code, "input_type": input_type}

    def _detect_inputs(self,
                       query: str,
                       *,
                       kind: str = "auto",
                       input_type: str = "auto") -> tuple[str, str]:
        try:
            clf = self.connector.classify("openai", query)
            kind = clf.get("kind", kind)
            input_type = clf.get("input_type", input_type)
        except Exception as e:
            print_warning(f"WARNING: failed to classify user intent with GPT. Using heuristic approach: {e}")
            pass  # go to default mode with not GPT query if errors occurs
        finally:
            return kind, input_type

    def help(self):
        print_text("""
        Perform a semantic search in the Laminar library. Proposes PEs and Workflows if it cannot find a match.
        """)

    def _search(self, query: str, *, kind: str = "auto", input_type: str = "auto",
                shortlist_n: int = 30, top_k: int = 3, silent: bool = False):

        if kind == "auto" or input_type == "auto":
            kind, input_type = self._detect_inputs(query, kind=kind, input_type=input_type)

        shortlist, _mode = self._retrieve(query, kind=kind, input_type=input_type, top_n=shortlist_n)

        if not shortlist:
            print_warning("No candidates found (check embeddings/FTS).")
            return None

        best = shortlist[0]
        second = shortlist[1]["score"] if len(shortlist) > 1 else -1.0
        gap = best["score"] - second if second >= 0 else 1.0

        # IMPORTANT: uncertainty based on embedding similarity, not compressed final score
        uncertain = (best["emb"] < 0.55) or (best["emb"] < 0.65 and gap < 0.04)

        # Only bail out (-> generation) when the match is genuinely weak. A
        # PE/either that is "uncertain" but still has a decent embedding (>= 0.40)
        # is good enough to surface, matching the original behaviour.
        if uncertain and (kind == "workflow" or best["emb"] < 0.40):
            if not silent:
                print_warning(
                    f"Could not find a strong match in the database "
                    f"(strongest match: {best['emb']}).")
            return None

        # Confident enough. Rerank (part of search) to pick the single best
        # ("suggested") candidate; display is then handed off to _present.
        reranked = self.connector.rerank(provider="openai", query=query,
                                         candidates=shortlist[:12], top_k=top_k)
        results = reranked.get("results", [])

        # Best suggested = the first reranked result mapped back to its shortlist
        # row; fall back to the top-scored row if rerank returned nothing.
        suggested = shortlist[0]
        if results:
            top = results[0]
            for c in shortlist:
                if c["type"] == top["type"] and c["id"] == int(top["id"]):
                    suggested = c
                    break

        suggested["tags"] = _safe_json_loads(suggested.get("tags_json"), [])

        if not silent:
            self._present(results, suggested)

        return shortlist

    def _present(self, results: list, suggested: dict):

        print_status("Top results (GPT reranked):\n")
        print_text(results, tab=True)

        print_status("Suggested candidate:\n")
        print_text([{
            "id": suggested["id"],
            "name": suggested["name"],
            "score": suggested["score"],
            "description": suggested["description"],
            "tags": suggested["tags"],
        }], tab=True)

        source = self._get_source(suggested.get("id"), suggested.get("type"))
        if source is not None:
            print_status("\nSource code:")
            print_code(source)

    def _generate(self, query: str, *, kind: str = "auto", input_type: str = "auto",
                  pe_top_n: int = 40, silent: bool = False):

        if kind == "auto" or input_type == "auto":
            kind, input_type = self._detect_inputs(query, kind=kind, input_type=input_type)

        if kind == "workflow":
            pe_only, _ = self._retrieve(query, kind="pe", input_type=input_type, top_n=pe_top_n)
            proposal = self.connector.propose_workflow_composition("openai", query, pe_only, max_fixes=2)

            print_status(f"{proposal.get('name')} - {proposal.get('description')}:\n")
            print_code(proposal.get("workflow_code"))

            if proposal.get("new_pe"):
                print_warning("\nNew PEs are required for this workflow:")
                for pe in proposal["new_pe"]:
                    print_text(f"{pe['name']} : {pe['description']}")

            if self._save_or_refine(code=proposal["workflow_code"],
                                    component_type="workflow", default_name=proposal.get("name", "workflow"),
                                    silent=silent):
                refinement_query = input("Provide additional information about the new workflow:")
                query = refine_prompt(proposal["workflow_code"], refinement_query, kind)
                return self._generate(query, kind=kind, input_type=input_type, pe_top_n=pe_top_n)
            else:
                return proposal

        # PE / either
        proposal = self.connector.propose_new_component(provider="openai", query=query)

        print_warning("Generating a new PE:\n")
        print_status(f"{proposal.get('name')} - {proposal.get('description')}\n")
        print_code(proposal.get("code"))

        if self._save_or_refine(code=proposal["code"], component_type="pe",
                                default_name=proposal.get("name", "pe"), silent=silent, ):
            refinement_query = input("Provide additional information about the new Processing Element:")
            query = refine_prompt(proposal["code"], refinement_query, kind)
            return self._generate(query, kind=kind, input_type=input_type, pe_top_n=pe_top_n)
        else:
            return proposal

    def _search_or_generate(self, query: str, *, kind: str = "auto", input_type: str = "auto",
                            shortlist_n: int = 30, top_k: int = 3, silent: bool = False):

        kind, input_type = self._detect_inputs(query, kind=kind, input_type=input_type)

        match = self._search(query, kind=kind, input_type=input_type,
                             shortlist_n=shortlist_n, top_k=top_k, silent=silent)
        if match is not None:
            return match

        return self._generate(query, kind=kind, input_type=input_type, silent=silent)

    def _get_source(self, result_id, kind: str = None):

        if kind == "pe":
            getters = (self.client.getPE, self.client.getWorkflow)
        elif kind == "workflow":
            getters = (self.client.getWorkflow, self.client.getPE)
        else:
            getters = (self.client.getWorkflow, self.client.getPE)

        for getter in getters:
            tmp = getter(result_id)
            if tmp:
                return tmp[1]
        return None

    def _save_or_refine(self, *, code: str, component_type: str,
                        default_name: str, silent: bool = False) -> bool:
        """Return true if another refinement is required, starting the loop again"""

        if silent:
            return False

        choice = (input(
            f"Would you like to refine / save the proposed {component_type}? "
            f"[(R)efine/(S)ave/(E)xit - Default Exit]: ") or "E").upper()

        if "R" in choice or "refine" in choice:
            return True
        elif "S" in choice or "save" in choice:
            filepath = input(
                f"Please input file path and filename to save the {component_type} code: "
            ) or f"{default_name}.py"
            with open(filepath, "w") as f:
                f.write(code)
            print_status(f"Stored {component_type} code to {filepath}")
            return False
        elif "E" in choice or "exit" in choice:
            return False
        else:
            print_warning(f"Unknown option: {choice}")
            return self._save_or_refine(code=code, component_type=component_type, silent=silent,
                                        default_name=default_name)

    def _run_query(self):
        query = input("Query: ")
        self._search_or_generate(query=query, input_type="auto", kind="", top_k=3)

    def search_library(self, arg):
        SearchTUI(self).run()


class PromptArea(TextArea):
    """Bottom input box. Submits on Enter and grows vertically (up to
    MAX_ROWS) as the typed text wraps onto more visual lines."""

    MAX_ROWS = 8

    class Submitted(Message):
        def __init__(self, value: str):
            self.value = value
            super().__init__()

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("soft_wrap", True)
        kwargs.setdefault("show_line_numbers", False)
        super().__init__(*args, **kwargs)

    def on_mount(self) -> None:
        self._resize()

    async def _on_key(self, event) -> None:
        # Enter submits instead of inserting a newline.
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.post_message(self.Submitted(self.text))
            return
        await super()._on_key(event)

    def on_text_area_changed(self, _event) -> None:
        self._resize()

    def _resize(self) -> None:
        rows = max(1, min(self.wrapped_document.height, self.MAX_ROWS))
        self.styles.height = rows + 2  # + top/bottom border


class SearchTUI(App):
    """Split-pane UI that drives AdvancedSearchCommand. The command's own
    print_*/input calls are routed here via the module-level routers above
    (this app registers itself as _ACTIVE_SINK for the session)."""

    CSS = """
    Screen { background: $surface; }

    #body { height: 1fr; }

    #left  { width: 55%; height: 1fr; }
    #right { width: 45%; height: 1fr; }

    #output {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
        background: $panel;
        /* keep the newest output (the current question) next to the input */
        align-vertical: bottom;
    }
    #right {
        border: round $secondary;
        padding: 0 1;
        background: $panel;
    }
    #prompt {
        height: 3;
        border: round $accent;
    }
    #prompt:disabled {
        opacity: 0.7;
    }
    """

    BINDINGS = [
        ("ctrl+l", "clear", "Clear panels"),
        ("ctrl+q", "request_quit", "Quit"),
        ("ctrl+c", "request_quit", "Quit"),
    ]

    def __init__(self, command: "AdvancedSearchCommand"):
        super().__init__()
        self.command = command
        self._answers: "queue.Queue[object]" = queue.Queue()
        self._awaiting = False
        self._busy_placeholder = "Working on it..."

    def compose(self) -> "ComposeResult":
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with Vertical(id="left"):
                out = VerticalScroll(id="output")
                out.border_title = "Search output"
                yield out
                prompt = PromptArea(id="prompt")
                prompt.border_title = "Input"
                yield prompt
            code = RichLog(id="right", wrap=False, highlight=False, markup=False)
            code.border_title = "Source code"
            yield code
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Laminar - Advanced Search"
        self._set_busy()
        self.run_session()

    @work(thread=True, exclusive=True)
    def run_session(self) -> None:
        global _ACTIVE_SINK
        _ACTIVE_SINK = self
        try:
            while True:
                self.call_from_thread(self._new_round)
                try:
                    self.command._run_query()
                except EOFError:
                    break  # app is quitting
                except Exception:
                    for ln in traceback.format_exc().splitlines():
                        self.call_from_thread(self._emit_output, (ln,), "bold red")
        finally:
            _ACTIVE_SINK = None

    # -- sink API called by the module-level routers (worker thread) -----
    def sink_text(self, *args, **kwargs):
        self.call_from_thread(self._emit_output, args, None)

    def sink_status(self, *args, **kwargs):
        self.call_from_thread(self._emit_output, args, "bold green")

    def sink_warning(self, *args, **kwargs):
        self.call_from_thread(self._emit_output, args, "bold yellow")

    def sink_error(self, *args, **kwargs):
        self.call_from_thread(self._emit_output, args, "bold red")

    def sink_code(self, code):
        self.call_from_thread(self._emit_code, code)

    def sink_ask(self, prompt: str) -> str:
        self.call_from_thread(self._set_prompt, prompt)
        answer = self._answers.get()  # blocks the worker thread
        if answer is _SHUTDOWN:
            raise EOFError
        return answer

    # -- widget mutations (UI thread) ------------------------------------
    def _append(self, renderable) -> None:
        out = self.query_one("#output", VerticalScroll)
        out.mount(Static(renderable))
        self.call_after_refresh(out.scroll_end, animate=False)

    def _emit_output(self, args, style):
        if not args:
            self._append(Text(""))
            return
        for a in args:
            if isinstance(a, str):
                self._append(Text(a.rstrip("\n"), style=style) if style else Text(a.rstrip("\n")))
            elif _is_table_like(a):
                self._append(_rows_to_table(a))  # <- new branch
            else:
                self._append(Pretty(a))

    def _emit_code(self, code):
        codelog = self.query_one("#right", RichLog)
        if code is None or code == "":
            codelog.write(Text("(no code)", style="dim italic"))
            return
        width = codelog.content_size.width or codelog.size.width
        codelog.write(
            Syntax(
                str(code),
                "python",
                theme="monokai",
                line_numbers=True,
                word_wrap=False,
                indent_guides=True,
            ),
            expand=True,
            width=width or None,
        )

    def _set_busy(self, message: str = None):
        """Disable the prompt while work is in progress."""
        inp = self.query_one("#prompt", PromptArea)
        message = message or self._busy_placeholder
        self._awaiting = False
        inp.disabled = True
        inp.border_title = "Input"

        # TextArea may not support placeholder in all Textual versions,
        # so fall back to showing the message as the text itself.
        if hasattr(inp, "placeholder"):
            inp.placeholder = message
            inp.text = ""
        else:
            inp.text = message

    def _set_prompt(self, prompt: str):
        clean = (prompt or "").strip()
        if clean:
            self._append(Text(clean, style="bold cyan"))

        inp = self.query_one("#prompt", PromptArea)
        inp.disabled = False

        if hasattr(inp, "placeholder"):
            inp.placeholder = ""

        inp.text = ""
        inp.border_title = (clean[:48] + "...") if len(clean) > 48 else (clean or "Input")
        inp.focus()
        self._awaiting = True

    def on_prompt_area_submitted(self, message: "PromptArea.Submitted") -> None:
        if not self._awaiting:
            return

        text = message.value
        self._append(Text(f"> {text}", style="bright_white"))
        self._set_busy()
        self._answers.put(text)

    def _new_round(self):
        self._append(Text("New search - answer the prompts below.", style="dim italic"))

    # -- actions ---------------------------------------------------------
    def action_clear(self):
        self.query_one("#output", VerticalScroll).remove_children()
        self.query_one("#right", RichLog).clear()
        pass

    def action_request_quit(self):
        self._answers.put(_SHUTDOWN)  # unblock the worker if it's in input()
        self.exit()
