"""Conservative AST-based inventory: no target source is imported or executed."""

import ast
import sys
from pathlib import Path


def _calls(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _evidence(path, line):
    return f"{path}:{line}"


def _module(path):
    return ".".join(path.with_suffix("").parts).removesuffix(".__init__")


def analyze(source):
    """Return a deterministic, evidence-linked assessment of Python source."""
    source = Path(source).resolve()
    if not source.exists() or not (source.is_file() or source.is_dir()):
        raise ValueError(f"source does not exist: {source}")
    if source.is_file() and source.suffix != ".py":
        raise ValueError("source must be a Python file or directory")
    root = source if source.is_dir() else source.parent
    paths = sorted(
        p for p in (root.rglob("*.py") if source.is_dir() else [source])
        if p.is_file() and not p.is_symlink() and not any(
            part.startswith(".") or part in {"__pycache__", "venv", "node_modules"}
            for part in p.relative_to(root).parts
        )
    )
    if not paths:
        raise ValueError("no Python files found")

    parsed = {}
    for path in paths:
        relative = path.relative_to(root).as_posix()
        parsed[_module(path.relative_to(root))] = (
            relative,
            ast.parse(path.read_text(encoding="utf-8"), filename=relative),
        )
    modules = set(parsed)
    behaviors, dependencies, risks, treatments = [], [], [], []
    for module, (path, tree) in sorted(parsed.items()):
        aliases = {}
        imports = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    aliases[alias.asname or alias.name.split(".")[0]] = alias.name
                    imports.append((alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    base = ".".join(filter(None, [module.rpartition(".")[0], base]))
                for alias in node.names:
                    aliases[alias.asname or alias.name] = ".".join(filter(None, [base, alias.name]))
                imports.append((base, node.lineno))
        for imported, line in imports:
            if imported:
                dependencies.append({
                    "from": module, "to": imported, "kind": "local" if imported in modules else "import",
                    "evidence": _evidence(path, line),
                })

        functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        local_names = {node.name for node in functions}
        signals = []
        for function in functions:
            observed = set()
            for call in _calls(function):
                target = _name(call.func)
                if not target:
                    continue
                head, _, tail = target.partition(".")
                resolved = aliases.get(head, head) + (f".{tail}" if tail else "")
                if head in local_names:
                    resolved = f"{module}.{target}"
                if resolved.rpartition(".")[0] in modules or (head in local_names):
                    dependencies.append({
                        "from": f"{module}.{function.name}", "to": resolved, "kind": "call",
                        "evidence": _evidence(path, call.lineno),
                    })
                if target.endswith(".execute") and call.args:
                    observed.add("database query")
                    query = call.args[0]
                    if isinstance(query, (ast.JoinedStr, ast.BinOp, ast.Call)):
                        risks.append({
                            "module": module, "risk": "Dynamically constructed SQL requires review for injection",
                            "evidence": _evidence(path, call.lineno), "severity": "high",
                        })
                if resolved == "sqlite3.connect":
                    observed.add("local SQLite persistence")
                    signals.append(("SQLite storage couples the module to a local database", call.lineno, "medium"))
                if resolved == "csv.writer":
                    observed.add("CSV generation")
                if target in {"open", "Path.open"} or target.endswith(".write_text"):
                    observed.add("file access")
                if target in {"eval", "exec"}:
                    signals.append(("Dynamic code execution prevents reliable static analysis", call.lineno, "high"))
            for node in ast.walk(function):
                if isinstance(node, ast.BinOp) and isinstance(
                    node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
                ):
                    observed.add("arithmetic calculation")
                if isinstance(node, ast.ExceptHandler) and (
                    node.type is None or _name(node.type) in {"Exception", "BaseException"}
                ):
                    signals.append(("Broad exception handling may hide failures", node.lineno, "medium"))
            behaviors.append({
                "function": f"{module}.{function.name}",
                "inferred_behavior": function.name.replace("_", " "),
                "observed_operations": sorted(observed) or ["internal computation or orchestration"],
                "evidence": _evidence(path, function.lineno),
            })
        for text, line, severity in signals:
            risks.append({"module": module, "risk": text, "evidence": _evidence(path, line), "severity": severity})

        own_risks = [risk for risk in risks if risk["module"] == module]
        own_deps = [dep for dep in dependencies if dep["from"] == module]
        external_deps = [
            dep for dep in own_deps
            if dep["kind"] == "import" and dep["to"].split(".")[0] not in sys.stdlib_module_names
        ]
        if not functions and not own_deps and path.endswith("__init__.py"):
            continue
        if any("Dynamic code" in risk["risk"] for risk in own_risks):
            treatment, reason = "rewrite", "Dynamic execution is not safely characterizable without isolation"
        elif any(risk["severity"] == "high" for risk in own_risks):
            treatment, reason = "refactor", "Unsafe query construction should be replaced before migration"
        elif any("SQLite" in risk["risk"] for risk in own_risks):
            treatment, reason = "replatform", "Local database coupling needs a managed persistence boundary"
        elif external_deps:
            treatment, reason = "rehost", "Non-standard-library imports need environment compatibility checks"
        else:
            treatment, reason = "retain", "No migration driver was detected by these static rules"
        evidence = ([risk["evidence"] for risk in own_risks] or
                    [dep["evidence"] for dep in external_deps] or
                    [_evidence(path, functions[0].lineno if functions else 1)])
        treatments.append({
            "module": module, "path": treatment, "reason": reason, "evidence": sorted(set(evidence)),
        })

    risks.sort(key=lambda r: (r["module"], r["evidence"], r["risk"]))
    dependencies.sort(key=lambda d: (d["from"], d["to"], d["evidence"]))
    backlog = [
        {"priority": "P1" if risk["severity"] == "high" else "P2",
         "action": f"Investigate and remediate: {risk['risk']}",
         "evidence": risk["evidence"], "module": risk["module"]}
        for risk in risks
    ]
    backlog += [
        {"priority": "P3", "action": f"Validate {item['path']} candidate for {item['module']}",
         "evidence": item["evidence"][0], "module": item["module"]}
        for item in treatments
    ]
    backlog.sort(key=lambda item: (item["priority"], item["module"], item["action"]))
    return {
        "scope": "Static Python inventory; names are hypotheses, not verified business requirements.",
        "files": [value[0] for _, value in sorted(parsed.items())],
        "behaviors": behaviors, "dependencies": dependencies, "risks": risks,
        "treatments": treatments, "backlog": backlog,
        "phases": [
            {"phase": "0 - Discover", "outcome": "Confirm inferred behavior with tests and stakeholders"},
            {"phase": "1 - Stabilize", "outcome": "Add characterization tests and isolate risky boundaries"},
            {"phase": "2 - Modernize", "outcome": "Implement validated treatment paths in dependency order"},
            {"phase": "3 - Verify", "outcome": "Compare business outcomes and operational measures before cutover"},
        ],
        "proof_of_value": {
            "files_scanned": len(parsed), "behaviors_identified": len(behaviors),
            "dependencies_mapped": len(dependencies), "risks_flagged": len(risks),
            "caveat": "Static signals are hypotheses; dynamic calls, runtime configuration, and actual business intent require validation.",
        },
    }


def render_report(result):
    """Render a concise, human-readable companion to the machine-readable assessment."""
    pov = result["proof_of_value"]
    lines = [
        "# Legacy application assessment", "",
        result["scope"], "",
        "## Proof of value", "",
        f"Scanned {pov['files_scanned']} files; identified {pov['behaviors_identified']} behavior candidates, "
        f"{pov['dependencies_mapped']} dependencies, and {pov['risks_flagged']} "
        f"risk {'signal' if pov['risks_flagged'] == 1 else 'signals'}.", "",
        pov["caveat"], "",
        "## Business behavior candidates", "",
    ]
    lines += [
        f"- **{b['function']}** ({b['evidence']}): {b['inferred_behavior']}; observed: {', '.join(b['observed_operations'])}"
        for b in result["behaviors"]
    ]
    lines += ["", "## Dependency map", ""]
    lines += [
        f"- {d['from']} → {d['to']} ({d['kind']}; {d['evidence']})"
        for d in result["dependencies"]
    ] or ["- No static dependencies detected."]
    lines += ["", "## Technical risks and treatment paths", ""]
    lines += [
        f"- {r['module']}: {r['risk']} ({r['severity']}; {r['evidence']})"
        for r in result["risks"]
    ] or ["- No risks detected by these rules."]
    lines += [
        f"- **{t['module']}: {t['path']}** — {t['reason']} ({', '.join(t['evidence'])})"
        for t in result["treatments"]
    ]
    lines += ["", "## Modernization backlog", ""]
    lines += [
        f"- {b['priority']}: {b['action']} ({b['evidence']})" for b in result["backlog"]
    ]
    lines += ["", "## Phased plan", ""]
    lines += [f"- **{p['phase']}**: {p['outcome']}" for p in result["phases"]]
    return "\n".join(lines) + "\n"
