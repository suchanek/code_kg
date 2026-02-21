#!/usr/bin/env python3
"""
codekg.py

Foundational code knowledge graph extractor.

Pure, deterministic AST pass:
    repo -> nodes, edges

NO persistence
NO embeddings
NO LLMs
NO Hindsight
NO guessing beyond explicit rules

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import ast
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# ============================================================================
# Graph primitives (LOCKED v0 CONTRACT)
# ============================================================================


@dataclass(frozen=True)
class Node:
    """
    Graph node.

    :param id: Stable node id (e.g. fn:pkg/util.py:parse_file)
    :param kind: module | class | function | method | symbol
    :param name: Short name
    :param qualname: Qualified name within module
    :param module_path: Repo-relative module path
    :param lineno: Starting line number
    :param end_lineno: Ending line number (if available)
    :param docstring: Extracted docstring (may be None)
    """

    id: str
    kind: str
    name: str
    qualname: str | None
    module_path: str | None
    lineno: int | None
    end_lineno: int | None
    docstring: str | None


@dataclass(frozen=True)
class Edge:
    """
    Graph edge.

    :param src: Source node id
    :param rel: Relationship type
    :param dst: Destination node id
    :param evidence: Optional evidence dict (lineno, expr, etc.)
    """

    src: str
    rel: str
    dst: str
    evidence: dict | None = None


# ============================================================================
# Constants
# ============================================================================

NODE_KINDS = {"module", "class", "function", "method", "symbol"}
EDGE_KINDS = {"CONTAINS", "IMPORTS", "INHERITS", "CALLS"}

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
}


# ============================================================================
# Utility helpers
# ============================================================================


def iter_python_files(repo_root: Path) -> Iterable[Path]:
    """
    Yield Python files under repo_root.

    :param repo_root: Repository root
    """
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            if f.endswith(".py") and not f.startswith("."):
                yield Path(root) / f


def rel_module_path(path: Path, repo_root: Path) -> str:
    """
    Convert file path to repo-relative module path.

    :param path: Absolute file path
    :param repo_root: Repo root
    """
    return str(path.relative_to(repo_root)).replace("\\", "/")


def node_id(kind: str, module: str, qualname: str | None) -> str:
    """
    Construct stable node id.

    :param kind: Node kind
    :param module: Repo-relative module path
    :param qualname: Qualified name
    """
    if kind == "module":
        return f"mod:{module}"

    prefix = {
        "class": "cls",
        "function": "fn",
        "method": "m",
        "symbol": "sym",
    }[kind]

    return f"{prefix}:{module}:{qualname}" if qualname else f"{prefix}:{module}"


def expr_to_name(expr: ast.AST) -> str | None:
    """
    Convert AST expression to dotted name (best effort).

    :param expr: AST node
    """
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        left = expr_to_name(expr.value)
        return f"{left}.{expr.attr}" if left else expr.attr
    if isinstance(expr, ast.Call):
        return expr_to_name(expr.func)
    if isinstance(expr, ast.Subscript):
        return expr_to_name(expr.value)
    return None


# ============================================================================
# Core extraction logic
# ============================================================================


def extract_repo(repo_root: Path) -> tuple[list[Node], list[Edge]]:
    """
    Extract a code knowledge graph from a repository.

    This function is:
    - pure
    - deterministic
    - side-effect free

    :param repo_root: Path to repository root
    :return: (nodes, edges)
    """
    nodes: dict[str, Node] = {}
    edges: dict[tuple[str, str, str], Edge] = {}

    # ------------------------------------------------------------------
    # PASS 1: modules, classes, functions, methods
    # ------------------------------------------------------------------

    module_locals: dict[str, dict[str, str]] = {}
    module_class_methods: dict[str, dict[str, str]] = {}

    for pyfile in iter_python_files(repo_root):
        module = rel_module_path(pyfile, repo_root)

        try:
            src = pyfile.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=module)
        except (SyntaxError, UnicodeDecodeError):
            continue

        # module node
        mod_id = node_id("module", module, None)
        nodes[mod_id] = Node(
            id=mod_id,
            kind="module",
            name=Path(module).stem,
            qualname=None,
            module_path=module,
            lineno=1,
            end_lineno=src.count("\n") + 1,
            docstring=ast.get_docstring(tree),
        )

        module_locals[module] = {}
        module_class_methods[module] = {}

        # traverse module body only (NOT ast.walk)
        for stmt in tree.body:
            # --------------------
            # class definitions
            # --------------------
            if isinstance(stmt, ast.ClassDef):
                cls_qn = stmt.name
                cls_id = node_id("class", module, cls_qn)

                nodes[cls_id] = Node(
                    id=cls_id,
                    kind="class",
                    name=stmt.name,
                    qualname=cls_qn,
                    module_path=module,
                    lineno=getattr(stmt, "lineno", None),
                    end_lineno=getattr(stmt, "end_lineno", None),
                    docstring=ast.get_docstring(stmt),
                )

                edges[(mod_id, "CONTAINS", cls_id)] = Edge(
                    src=mod_id,
                    rel="CONTAINS",
                    dst=cls_id,
                )

                module_locals[module][stmt.name] = cls_id

                # inheritance
                for base in stmt.bases:
                    bname = expr_to_name(base)
                    if not bname:
                        continue
                    sym_id = f"sym:{bname}"
                    nodes.setdefault(
                        sym_id,
                        Node(
                            sym_id,
                            "symbol",
                            bname.split(".")[-1],
                            bname,
                            None,
                            None,
                            None,
                            None,
                        ),
                    )
                    edges[(cls_id, "INHERITS", sym_id)] = Edge(
                        src=cls_id,
                        rel="INHERITS",
                        dst=sym_id,
                        evidence={"lineno": getattr(stmt, "lineno", None)},
                    )

                # methods
                for cstmt in stmt.body:
                    if isinstance(cstmt, ast.FunctionDef | ast.AsyncFunctionDef):
                        m_qn = f"{stmt.name}.{cstmt.name}"
                        m_id = node_id("method", module, m_qn)

                        nodes[m_id] = Node(
                            id=m_id,
                            kind="method",
                            name=cstmt.name,
                            qualname=m_qn,
                            module_path=module,
                            lineno=getattr(cstmt, "lineno", None),
                            end_lineno=getattr(cstmt, "end_lineno", None),
                            docstring=ast.get_docstring(cstmt),
                        )

                        edges[(cls_id, "CONTAINS", m_id)] = Edge(
                            src=cls_id,
                            rel="CONTAINS",
                            dst=m_id,
                        )

                        module_class_methods[module][cstmt.name] = m_id
                        module_locals[module][m_qn] = m_id

            # --------------------
            # top-level functions
            # --------------------
            elif isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
                fn_qn = stmt.name
                fn_id = node_id("function", module, fn_qn)

                nodes[fn_id] = Node(
                    id=fn_id,
                    kind="function",
                    name=stmt.name,
                    qualname=fn_qn,
                    module_path=module,
                    lineno=getattr(stmt, "lineno", None),
                    end_lineno=getattr(stmt, "end_lineno", None),
                    docstring=ast.get_docstring(stmt),
                )

                edges[(mod_id, "CONTAINS", fn_id)] = Edge(
                    src=mod_id,
                    rel="CONTAINS",
                    dst=fn_id,
                )

                module_locals[module][stmt.name] = fn_id

            # --------------------
            # imports
            # --------------------
            elif isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    sym = alias.name
                    sym_id = f"sym:{sym}"
                    nodes.setdefault(
                        sym_id,
                        Node(
                            sym_id,
                            "symbol",
                            sym.split(".")[-1],
                            sym,
                            None,
                            None,
                            None,
                            None,
                        ),
                    )
                    edges[(mod_id, "IMPORTS", sym_id)] = Edge(
                        src=mod_id,
                        rel="IMPORTS",
                        dst=sym_id,
                        evidence={"lineno": getattr(stmt, "lineno", None)},
                    )

            elif isinstance(stmt, ast.ImportFrom):
                mod = stmt.module or ""
                for alias in stmt.names:
                    full = f"{mod}.{alias.name}" if mod else alias.name
                    sym_id = f"sym:{full}"
                    nodes.setdefault(
                        sym_id,
                        Node(sym_id, "symbol", alias.name, full, None, None, None, None),
                    )
                    edges[(mod_id, "IMPORTS", sym_id)] = Edge(
                        src=mod_id,
                        rel="IMPORTS",
                        dst=sym_id,
                        evidence={"lineno": getattr(stmt, "lineno", None)},
                    )

        # ------------------------------------------------------------------
        # PASS 2: call graph (best-effort, honest)
        # ------------------------------------------------------------------

        parent: dict[ast.AST, ast.AST] = {}
        for p in ast.walk(tree):
            for c in ast.iter_child_nodes(p):
                parent[c] = p

        def enclosing_def(n: ast.AST) -> ast.AST | None:
            cur = parent.get(n)
            while cur:
                if isinstance(cur, ast.FunctionDef | ast.AsyncFunctionDef):
                    return cur
                cur = parent.get(cur)
            return None

        def owner_id(fn: ast.AST) -> str | None:
            p = parent.get(fn)
            if isinstance(p, ast.ClassDef):
                return module_locals[module].get(f"{p.name}.{fn.name}")
            return module_locals[module].get(fn.name)

        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue

            fn = enclosing_def(n)
            if fn is None:
                continue

            src_id = owner_id(fn)
            if not src_id:
                continue

            callee = expr_to_name(n.func)
            if not callee:
                continue

            # resolution rules (LOCKED)
            if callee in module_locals[module]:
                dst_id = module_locals[module][callee]
            elif callee.startswith("self."):
                meth = callee.split(".", 1)[1]
                dst_id = module_class_methods[module].get(meth)
                if not dst_id:
                    dst_id = f"sym:{callee}"
            else:
                dst_id = f"sym:{callee}"

            if dst_id.startswith("sym:"):
                nodes.setdefault(
                    dst_id,
                    Node(
                        dst_id,
                        "symbol",
                        dst_id.split(":")[-1].split(".")[-1],
                        dst_id[4:],
                        None,
                        None,
                        None,
                        None,
                    ),
                )

            edges[(src_id, "CALLS", dst_id)] = Edge(
                src=src_id,
                rel="CALLS",
                dst=dst_id,
                evidence={
                    "lineno": getattr(n, "lineno", None),
                    "expr": callee,
                },
            )

    return list(nodes.values()), list(edges.values())
