"""CI guard: no `_` prefix on module/class scope identifiers in src/.

The project rule: every public symbol is a single word with no underscore.
Private symbols are signaled by *location* (module name, class scope) — not
by a leading underscore on the identifier itself. The only accepted
underscore identifiers in src/ are:

- Dunder names: `__init__`, `__aenter__`, `__aexit__`, `__contains__`,
  `__repr__`, `__str__`, `__dict__`, etc.
- Module-internal constants like `_CONFIGURED` (we no longer use any).
- The `_internal.py` module name (the underscore in the *module name*
  signals private boundary, not private identifier).

If you find a `_` identifier outside these cases, rename it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ALLOWED_DUNDER = {
    "__init__",
    "__aenter__",
    "__aexit__",
    "__contains__",
    "__repr__",
    "__str__",
    "__iter__",
    "__next__",
    "__len__",
    "__getitem__",
    "__setitem__",
    "__delitem__",
    "__getattr__",
    "__setattr__",
    "__delattr__",
    "__call__",
    "__enter__",
    "__exit__",
    "__hash__",
    "__eq__",
    "__lt__",
    "__le__",
    "__gt__",
    "__ge__",
    "__ne__",
    "__add__",
    "__sub__",
    "__mul__",
    "__truediv__",
    "__floordiv__",
    "__mod__",
    "__pow__",
    "__and__",
    "__or__",
    "__xor__",
    "__neg__",
    "__pos__",
    "__abs__",
    "__bool__",
    "__int__",
    "__float__",
    "__dict__",
    "__class__",
    "__bases__",
    "__name__",
    "__qualname__",
    "__module__",
    "__defaults__",
    "__code__",
    "__globals__",
    "__closure__",
    "__annotations__",
    "__kwdefaults__",
    "__doc__",
    "__init_subclass__",
    "__class_getitem__",
    "__new__",
    "__missing__",
    "__set_name__",
    "__path__",
    "__loader__",
    "__spec__",
    "__subclasshook__",
    "__all__",
}


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__") and name in ALLOWED_DUNDER


def _is_module_private_module_path(path: Path) -> bool:
    """`_internal.py` is allowed (underscore-in-filename is fine)."""
    return path.name == "_internal.py"


def _walk_identifier_violations(tree: ast.AST, source_path: Path) -> list[str]:
    """Walk an AST and return a list of `_`-prefixed identifiers at module/class scope."""
    violations: list[str] = []

    def visit(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Module or class-scope function definition.
                if scope in {"module", "class"} and child.name.startswith("_") and not _is_dunder(child.name):
                    violations.append(
                        f"{source_path}:{child.lineno}: {child.name} (function)"
                    )
                # Always recurse into nested defs (they're local scope).
                visit(child, "function")

            elif isinstance(child, ast.ClassDef):
                # Class def: it's public by default; only dunder allowed for `_`-prefixed names.
                if child.name.startswith("_") and not _is_dunder(child.name):
                    violations.append(f"{source_path}:{child.lineno}: class {child.name}")
                visit(child, "class")

            elif isinstance(child, ast.Assign):
                # Module/class-level variable assignments.
                if scope in {"module", "class"}:
                    for target in child.targets:
                        if isinstance(target, ast.Name) and target.id.startswith("_") and not _is_dunder(target.id):
                            violations.append(
                                f"{source_path}:{child.lineno}: variable {target.id}"
                            )

            elif isinstance(child, ast.AnnAssign):
                if scope in {"module", "class"}:
                    target = child.target
                    if isinstance(target, ast.Name) and target.id.startswith("_") and not _is_dunder(target.id):
                        violations.append(
                            f"{source_path}:{child.lineno}: variable {target.id}"
                        )

    visit(tree, "module")
    return violations


def test_no_underscore_prefix_in_src() -> None:
    """All module/class-scope identifiers in src/docendo/ must be underscore-free.

    Allowed: dunder (`__init__`, etc.), the `_internal.py` module name, and
    `instance attributes` (e.g., `self._lock`, `self._conn`).
    """
    src = Path("src/docendo")
    if not src.exists():
        pytest.skip("src/docendo not present")

    all_violations: list[str] = []
    for path in sorted(src.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if _is_module_private_module_path(path):
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError as exc:
            all_violations.append(f"{path}: SyntaxError: {exc}")
            continue
        all_violations.extend(_walk_identifier_violations(tree, path))

    assert not all_violations, (
        "Underscore-prefixed identifiers at module/class scope in src/docendo/:\n"
        + "\n".join(f"  {v}" for v in all_violations)
        + "\n\nRename these to single-word, no-underscore names. The project rule:\n"
        "single-word public names; privacy is signaled by *location* (module name,\n"
        "class scope), not by a leading `_` on the identifier."
    )
