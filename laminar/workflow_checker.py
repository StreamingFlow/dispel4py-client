import re


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
                source_code):
            ports.append((m.group(1), m.group(2), m.group(3), m.group(4)))
        for m in re.finditer(
                r'graph\.connect\(\s*([a-zA-Z_]\w*)\s*,\s*"([^"]+)"\s*,\s*([a-zA-Z_]\w*)\s*,\s*"([^"]+)"\s*\)',
                source_code):
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

    if not code or ("WorkflowGraph" not in code) or ("graph.connect" not in code):
        issues.append("Missing WorkflowGraph or graph.connect")
    if not contains_sink_step(code):
        issues.append("Missing sink/write step (workflow should write results)")
    if has_suspicious_ports(code):
        issues.append("Uses non-standard ports (likely invented). Prefer 'output'->'input'")

    return len(issues) == 0, issues
