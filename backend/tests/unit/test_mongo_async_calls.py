"""PyMongo async returns cursors from coroutines: every aggregate()/list_indexes() must be awaited.

Motor returned them synchronously, so a missed `await` passes imports and fails only at runtime.
"""

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
COROUTINE_CURSOR_METHODS = {"aggregate", "list_indexes"}


def test_every_cursor_call_is_awaited():
    offenders = []
    for root in ("app", "scripts", "tests"):
        for path in (BACKEND_DIR / root).rglob("*.py"):
            if "unit" in path.relative_to(BACKEND_DIR).parts:
                continue  # unit tests define mock aggregate() methods, not real calls
            tree = ast.parse(path.read_text())
            awaited = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Await)}
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in COROUTINE_CURSOR_METHODS
                    and id(node) not in awaited
                ):
                    offenders.append(f"{path.relative_to(BACKEND_DIR)}:{node.lineno}")
    assert offenders == []
