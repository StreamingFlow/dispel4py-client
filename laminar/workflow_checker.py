import re
import ast

from laminar.screen_printer import print_warning


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

    class JSONSerializableChecker(ast.NodeVisitor):
        def __init__(self, source_code_lines):
            self.non_serializable_lines = []
            self.code_lines = source_code_lines
            self.dict_vars = set()

        def visit_Assign(self, node):
            # Track variables assigned from dict lookups (e.g., result = data['key'])
            if isinstance(node.value, ast.Subscript):
                if isinstance(node.value.value, ast.Name):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.dict_vars.add(target.id)
            self.generic_visit(node)

        def visit_Call(self, node):
            # Detect self.write(...) calls
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                    if node.func.attr == "write":
                        for node_arg in node.args:
                            if not self.is_json_serializable(node_arg):
                                self.non_serializable_lines.append(
                                    (node.lineno, self.code_lines[node.lineno - 1].strip()))
            self.generic_visit(node)

        def is_json_serializable(self, node):
            # Treat variables assigned from dict lookups as serializable
            if isinstance(node, ast.Name) and node.id in self.dict_vars:
                return True
            if isinstance(node, ast.Constant):
                return isinstance(node.value, (str, int, float, bool, type(None)))
            elif isinstance(node, (ast.List, ast.Tuple)):
                return all(self.is_json_serializable(elt) for elt in node.elts)
            elif isinstance(node, ast.Dict):
                for key, v in zip(node.keys, node.values):
                    if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                        return False
                    if not self.is_json_serializable(v):
                        return False
                return True

            elif isinstance(node, ast.Subscript):
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
