import ast
import json
import subprocess
import sys

from modernizer.graph.state import PipelineState
from modernizer.validation.execution import check_execution


def validate_node(state: PipelineState) -> dict:
    code = state.get("generated_code") or ""
    name = state["parsed"]["name"]

    tree, errors = _check_syntax(code)
    checks = {"syntax": not errors}

    if tree is not None:
        structure = _check_structure(tree, name)
        lint = _check_lint(code)
        checks["structure"] = not structure
        checks["lint"] = not lint
        errors += structure + lint
        if not structure:
            execution = check_execution(code, state["parsed"])
            if execution is not None:
                checks["execution"] = not execution
                errors += execution

    return {
        "validation": {"checks": checks, "errors": errors},
        "status": "sucesso" if not errors else "parcial",
    }


def _check_syntax(code: str) -> tuple[ast.Module | None, list[str]]:
    try:
        return ast.parse(code), []
    except SyntaxError as exc:
        return None, [f"sintaxe: linha {exc.lineno}: {exc.msg}"]


def _check_structure(tree: ast.Module, name: str) -> list[str]:
    errors: list[str] = []
    if ast.get_docstring(tree) is None:
        errors.append("estrutura: o modulo nao tem docstring na primeira linha, antes dos imports")
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    main = functions.get(name)
    if main is None:
        errors.append(f"estrutura: funcao principal '{name}' nao encontrada")
    elif not main.args.args or main.args.args[0].arg != "conn":
        errors.append(f"estrutura: o primeiro parametro de '{name}' deve ser 'conn'")
    return errors


def _check_lint(code: str) -> list[str]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--no-cache",
            "--select",
            "E9,F",
            "--output-format",
            "json",
            "--stdin-filename",
            "generated.py",
            "-",
        ],
        input=code,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        findings = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return [f"lint: ruff falhou: {result.stderr.strip()}"]
    return [f"lint: {f.get('code')} linha {f['location']['row']}: {f['message']}" for f in findings]
