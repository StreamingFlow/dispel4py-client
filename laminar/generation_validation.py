"""Static checks for generated code; never execute an LLM proposal to inspect it."""
import ast
import textwrap


def classes(source):
    return {node.name: node for node in ast.parse(textwrap.dedent(source)).body
            if isinstance(node, ast.ClassDef)}


def inspect_generated(source, candidates=(), uses_pes=()):
    issues, placeholders = [], []
    try:
        generated = classes(source)
    except (SyntaxError, TypeError) as exc:
        return [f"Invalid Python: {exc}"], []
    pe_names = {"GenericPE", "IterativePE", "ProducerPE", "ConsumerPE", "BasePE"}
    for name, cls in generated.items():
        bases = {getattr(base, "id", getattr(base, "attr", "")) for base in cls.bases}
        methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
        if bases & pe_names and "process" in methods:
            issues.append(f"{name}: implement _process, not process; process is a framework method.")
        for method in methods.values():
            for node in ast.walk(method):
                if isinstance(node, ast.Raise):
                    exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
                    if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                        placeholders.append(f"{name}.{method.name}")
    available = {candidate["name"]: candidate for candidate in candidates}
    for name in set(uses_pes or ()) | (set(generated) & set(available)):
        candidate = available.get(name)
        if candidate is None:
            issues.append(f"Claimed reused PE {name} is not in the supplied candidates.")
            continue
        try:
            original = classes(candidate.get("source_code") or "").get(name)
        except SyntaxError:
            original = None
        if original is None:
            issues.append(f"Source for reused PE {name} is unavailable; do not claim exact reuse.")
        elif name not in generated:
            issues.append(f"Include the supplied source class for reused PE {name}.")
        elif ast.dump(original, include_attributes=False) != ast.dump(generated[name], include_attributes=False):
            issues.append(f"Reused PE {name} differs from its registered source. Copy its class unchanged.")
    return issues, sorted(set(placeholders))
