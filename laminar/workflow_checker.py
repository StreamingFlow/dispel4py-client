import re
import ast

from laminar.screen_printer import print_warning

import ast


class JSONSerializableChecker(ast.NodeVisitor):
    """
    Heuristic lint for dispel4py PEs: flag ``self.write(stream, value)`` calls
    whose ``value`` is *known* to be non-serializable.

    A value is assumed serializable unless it (or a variable it flows from)
    is produced by a *known* non-serializable source
    (HTTP responses, BeautifulSoup nodes, file handles, sets, generators,
    bytes, lambdas, ...). That keeps false positives near zero, which is what
    you want from a warning that fires on every workflow, while still catching
    the patterns that actually break serialization.

    It tracks provenance with proper per-function scoping, so a variable that is
    tainted in one PE does not leak into another, and it follows taint through:
      * assignment            ``r = requests.get(u)``        -> ``r`` tainted
      * container mutation    ``out.append(soup.find('a'))`` -> ``out`` tainted
      * nesting               ``self.write('o', {'k': r})``  -> flagged

    Known blind spots (accepted to keep false positives low):
      * ``list(soup.find_all(...))`` -- list() rescues container *kind*, not
        element type, so a list of Tags slips through.
      * ``session.get(url)`` -- ``.get`` is indistinguishable from ``dict.get``
        / ``tag.get`` statically, so it is treated as safe.
    """

    # --- calls whose return value is non-serializable (matched on full name) --
    NON_SERIALIZABLE_CALLS = {
        "set", "frozenset", "bytes", "bytearray",
        "map", "filter", "zip", "iter", "reversed", "enumerate",
        "open", "object",
        "BeautifulSoup", "bs4.BeautifulSoup",
        "requests.get", "requests.post", "requests.put", "requests.patch",
        "requests.delete", "requests.head", "requests.request",
    }

    # --- methods (matched on attribute name) that return non-serializable objs -
    NON_SERIALIZABLE_METHODS = {"find_all", "findAll", "select", "select_one"}
    NON_SERIALIZABLE_ATTRS = {"content", "raw"}  # e.g. response.content -> bytes

    RESCUE_CALLS = {
        "str", "repr", "int", "float", "bool", "len",
        "list", "dict", "tuple", "sorted",
        "json.dumps", "json.dump", "format", "hex", "bin", "oct",
    }

    RESCUE_METHODS = {
        "json", "get", "get_text", "text", "string", "strip", "split", "rsplit",
        "splitlines", "join", "replace", "lower", "upper", "title", "capitalize",
        "format", "decode", "isoformat", "strftime", "tolist", "to_dict",
        "keys", "values", "items",
    }

    MUTATORS = {"append", "extend", "insert", "add", "update"}

    def __init__(self, source_code_lines):
        self.code_lines = source_code_lines
        self.non_serializable_lines = []
        self._scopes = [set()]

    @property
    def _tainted(self):
        return self._scopes[-1]

    def visit_FunctionDef(self, node):
        self._scopes.append(set())
        self.generic_visit(node)
        self._scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def _set_taint(self, name, tainted):
        if tainted:
            self._tainted.add(name)
        else:
            self._tainted.discard(name)

    @staticmethod
    def _dotted_name(node):
        """Best-effort dotted name for a Name/Attribute chain (e.g. requests.get)."""
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
            return ".".join(reversed(parts))
        return None

    def _is_non_serializable(self, node):
        """True if the *value* produced by ``node`` is known to be non-serializable."""
        if node is None:
            return False

        if isinstance(node, ast.Constant):
            return isinstance(node.value, (bytes, bytearray, complex)) or node.value is Ellipsis

        if isinstance(node, ast.Name):
            return node.id in self._tainted

        if isinstance(node, (ast.Set, ast.SetComp, ast.GeneratorExp, ast.Lambda)):
            return True

        if isinstance(node, (ast.List, ast.Tuple)):
            return any(self._is_non_serializable(e) for e in node.elts)

        if isinstance(node, ast.ListComp):
            return self._is_non_serializable(node.elt)

        if isinstance(node, ast.Dict):
            vals = any(self._is_non_serializable(v) for v in node.values)
            keys = any(self._is_non_serializable(k) for k in node.keys if k is not None)
            return vals or keys

        if isinstance(node, ast.DictComp):
            return self._is_non_serializable(node.value) or self._is_non_serializable(node.key)

        if isinstance(node, (ast.JoinedStr, ast.Compare, ast.BoolOp)):
            return False
        if isinstance(node, ast.BinOp):
            return self._is_non_serializable(node.left) or self._is_non_serializable(node.right)
        if isinstance(node, ast.IfExp):
            return self._is_non_serializable(node.body) or self._is_non_serializable(node.orelse)

        if isinstance(node, ast.Attribute):
            if node.attr in self.RESCUE_METHODS:
                return False
            if node.attr in self.NON_SERIALIZABLE_ATTRS:
                return True
            return self._is_non_serializable(node.value)

        if isinstance(node, ast.Subscript):
            return self._is_non_serializable(node.value)

        if isinstance(node, ast.Call):
            return self._call_is_non_serializable(node)

        return False

    def _call_is_non_serializable(self, node):
        func = node.func
        dotted = self._dotted_name(func)
        attr = func.attr if isinstance(func, ast.Attribute) else None

        # 1. Known-bad producers win first, even when the method name collides
        #    with a rescue (requests.get must beat the dict/tag .get rescue).
        if dotted in self.NON_SERIALIZABLE_CALLS:
            return True
        if dotted in self.RESCUE_CALLS or attr in self.RESCUE_METHODS:
            return False
        if attr in self.NON_SERIALIZABLE_METHODS:
            return True
        return False

    def _record(self, lineno):
        if 0 <= lineno - 1 < len(self.code_lines):
            text = self.code_lines[lineno - 1].strip()
        else:
            text = ""
        self.non_serializable_lines.append((lineno, text))

    def visit_Assign(self, node):
        self.generic_visit(node)
        bad = self._is_non_serializable(node.value)
        for target in node.targets:
            self._bind_target(target, bad)

    def visit_AnnAssign(self, node):
        self.generic_visit(node)
        if node.value is not None and isinstance(node.target, ast.Name):
            self._set_taint(node.target.id, self._is_non_serializable(node.value))

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        if isinstance(node.target, ast.Name) and self._is_non_serializable(node.value):
            self._tainted.add(node.target.id)

    def visit_For(self, node):
        if isinstance(node.target, ast.Name):
            self._set_taint(node.target.id, self._is_non_serializable(node.iter))
        self.generic_visit(node)

    def _bind_target(self, target, bad):
        if isinstance(target, ast.Name):
            self._set_taint(target.id, bad)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._bind_target(elt, bad)
        elif isinstance(target, ast.Subscript):
            base = target.value
            if isinstance(base, ast.Name) and bad:
                self._tainted.add(base.id)

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            # self.write('stream', value, ...) -> arg 0 is the stream name
            if func.attr == "write" and func.value.id == "self":
                flagged = any(self._is_non_serializable(a) for a in node.args[1:])
                flagged = flagged or any(
                    self._is_non_serializable(kw.value)
                    for kw in node.keywords if kw.arg in (None, "data")
                )
                if flagged:
                    self._record(node.lineno)

            # out.append(soup.find('a')) / d.update(...) -> taint the receiver
            elif func.attr in self.MUTATORS:
                if any(self._is_non_serializable(a) for a in node.args):
                    self._tainted.add(func.value.id)

        self.generic_visit(node)


def is_valid_workflow_code(code: str) -> tuple[bool, list[str]]:
    sink_hint_keywords = ["write", "sink", "jsonl", "csv", "parquet", "output"]
    common_port_hint = {"input", "output", "row", "rows"}

    def contains_sink_step(source_code: str) -> bool:
        c = (source_code or "").lower()
        return any(h in c for h in sink_hint_keywords)

    def extract_connect_ports(source_code: str):
        ports = []
        for m in re.finditer(
                r"graph\.connect\(\s*([a-zA-Z_]\w*)\s*,\s*'([^']+)'\s*,\s*([a-zA-Z_]\w*)\s*,\s*'([^']+)'\s*\)",
                source_code,
        ):
            ports.append((m.group(1), m.group(2), m.group(3), m.group(4)))
        for m in re.finditer(
                r'graph\.connect\(\s*([a-zA-Z_]\w*)\s*,\s*"([^"]+)"\s*,\s*([a-zA-Z_]\w*)\s*,\s*"([^"]+)"\s*\)',
                source_code,
        ):
            ports.append((m.group(1), m.group(2), m.group(3), m.group(4)))
        return ports

    def has_suspicious_ports(source_code: str) -> bool:
        for _, outp, _, inp in extract_connect_ports(source_code):
            if outp not in common_port_hint:
                return True
            if inp not in common_port_hint:
                return True
        return False

    issues = []

    try:
        compile(code, "<string>", "exec")
    except Exception as e:
        issues.append(f"Invalid Python code: {e}")

    if not code or ("WorkflowGraph" not in code):
        issues.append("Missing WorkflowGraph")

    if not code or (".connect" not in code):
        issues.append("Missing graph.connect")

    if not contains_sink_step(code):
        issues.append("Missing sink/write step (workflow should write results)")

    if has_suspicious_ports(code):
        issues.append("Uses non-standard ports (likely invented). Prefer 'output'->'input'")

    try:
        tree = ast.parse(code)
        code_lines = code.splitlines()
        checker = JSONSerializableChecker(code_lines)
        checker.visit(tree)
        for lineno, line_text in checker.non_serializable_lines:
            issues.append(
                f"Non-JSON-serializable argument passed to self.write() at line {lineno}: {line_text}"
            )
    except Exception as e:
        issues.append(f"Failed AST JSON check: {e}")

    # Print all issues
    for issue in issues:
        print_warning(issue)

    return len(issues) == 0, issues
