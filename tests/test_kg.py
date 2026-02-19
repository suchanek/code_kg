"""
test_kg.py

Tests for CodeKG orchestrator and result types:
  BuildStats, QueryResult, SnippetPack, CodeKG
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from code_kg.kg import (
    BuildStats,
    CodeKG,
    QueryResult,
    Snippet,
    SnippetPack,
    _compute_span,
    _make_snippet,
    _safe_join,
    _spans_overlap,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_repo(tmp_path: Path, files: dict) -> Path:
    for rel, src in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(src))
    return tmp_path


def _make_kg(tmp_path: Path, files: dict) -> CodeKG:
    """Build a CodeKG (graph only, no LanceDB) from a synthetic repo."""
    repo = tmp_path / "repo"
    _write_repo(repo, files)
    kg = CodeKG(
        repo_root=repo,
        db_path=tmp_path / "codekg.sqlite",
        lancedb_dir=tmp_path / "lancedb",
    )
    kg.build_graph(wipe=True)
    return kg


# ---------------------------------------------------------------------------
# BuildStats
# ---------------------------------------------------------------------------


def test_buildstats_to_dict(tmp_path):
    kg = _make_kg(tmp_path, {"mod.py": "def foo(): pass\n"})
    s = kg.store.stats()
    bs = BuildStats(
        repo_root=str(tmp_path),
        db_path=str(tmp_path / "codekg.sqlite"),
        total_nodes=s["total_nodes"],
        total_edges=s["total_edges"],
        node_counts=s["node_counts"],
        edge_counts=s["edge_counts"],
    )
    d = bs.to_dict()
    assert "total_nodes" in d
    assert "node_counts" in d
    kg.close()


def test_buildstats_str(tmp_path):
    kg = _make_kg(tmp_path, {"mod.py": "def foo(): pass\n"})
    s = kg.store.stats()
    bs = BuildStats(
        repo_root=str(tmp_path),
        db_path=str(tmp_path / "codekg.sqlite"),
        total_nodes=s["total_nodes"],
        total_edges=s["total_edges"],
        node_counts=s["node_counts"],
        edge_counts=s["edge_counts"],
        indexed_rows=42,
        index_dim=384,
    )
    text = str(bs)
    assert "indexed" in text
    assert "42" in text
    kg.close()


# ---------------------------------------------------------------------------
# CodeKG — build_graph
# ---------------------------------------------------------------------------


def test_codekg_build_graph_returns_buildstats(tmp_path):
    kg = _make_kg(tmp_path, {"mod.py": "def foo(): pass\n"})
    assert isinstance(kg.store.stats(), dict)
    kg.close()


def test_codekg_build_graph_populates_store(tmp_path):
    kg = _make_kg(
        tmp_path,
        {"mod.py": "class Foo:\n    def run(self): pass\ndef bar(): pass\n"},
    )
    s = kg.store.stats()
    assert s["total_nodes"] > 0
    assert s["total_edges"] > 0
    assert s["node_counts"].get("class", 0) >= 1
    assert s["node_counts"].get("function", 0) >= 1
    assert s["node_counts"].get("method", 0) >= 1
    kg.close()


def test_codekg_build_graph_wipe(tmp_path):
    kg = _make_kg(tmp_path, {"mod.py": "def foo(): pass\n"})
    count1 = kg.store.stats()["total_nodes"]
    kg.build_graph(wipe=True)
    count2 = kg.store.stats()["total_nodes"]
    assert count1 == count2  # same repo → same count
    kg.close()


# ---------------------------------------------------------------------------
# CodeKG — layer accessors
# ---------------------------------------------------------------------------


def test_codekg_graph_property(tmp_path):
    from code_kg.graph import CodeGraph

    kg = _make_kg(tmp_path, {"mod.py": "x = 1\n"})
    assert isinstance(kg.graph, CodeGraph)
    kg.close()


def test_codekg_store_property(tmp_path):
    from code_kg.store import GraphStore

    kg = _make_kg(tmp_path, {"mod.py": "x = 1\n"})
    assert isinstance(kg.store, GraphStore)
    kg.close()


def test_codekg_node_method(tmp_path):
    kg = _make_kg(tmp_path, {"mod.py": "def foo(): pass\n"})
    fns = kg.store.query_nodes(kinds=["function"])
    assert fns
    n = kg.node(fns[0]["id"])
    assert n is not None
    assert n["kind"] == "function"
    kg.close()


def test_codekg_stats(tmp_path):
    kg = _make_kg(tmp_path, {"mod.py": "def foo(): pass\n"})
    s = kg.stats()
    assert "total_nodes" in s
    kg.close()


def test_codekg_context_manager(tmp_path):
    repo = tmp_path / "repo"
    _write_repo(repo, {"mod.py": "x = 1\n"})
    with CodeKG(repo, tmp_path / "codekg.sqlite", tmp_path / "lancedb") as kg:
        kg.build_graph(wipe=True)
        assert kg.stats()["total_nodes"] > 0


def test_codekg_repr(tmp_path):
    kg = CodeKG(tmp_path, tmp_path / "db.sqlite", tmp_path / "ldb")
    r = repr(kg)
    assert "CodeKG" in r
    assert "repo_root" in r


# ---------------------------------------------------------------------------
# QueryResult
# ---------------------------------------------------------------------------


def test_queryresult_to_dict():
    qr = QueryResult(
        query="test",
        seeds=3,
        expanded_nodes=10,
        returned_nodes=5,
        hop=1,
        rels=["CONTAINS", "CALLS"],
        nodes=[{"id": "fn:mod.py:foo", "kind": "function", "name": "foo",
                "qualname": "foo", "module_path": "mod.py",
                "lineno": 1, "end_lineno": 3, "docstring": None}],
        edges=[],
    )
    d = qr.to_dict()
    assert d["query"] == "test"
    assert d["seeds"] == 3
    assert len(d["nodes"]) == 1


def test_queryresult_to_json():
    qr = QueryResult(
        query="test", seeds=1, expanded_nodes=2, returned_nodes=1,
        hop=1, rels=["CALLS"], nodes=[], edges=[],
    )
    text = qr.to_json()
    parsed = json.loads(text)
    assert parsed["query"] == "test"


# ---------------------------------------------------------------------------
# SnippetPack
# ---------------------------------------------------------------------------


def test_snippetpack_to_dict():
    sp = SnippetPack(
        query="q", seeds=1, expanded_nodes=2, returned_nodes=1,
        hop=1, rels=["CALLS"], model="all-MiniLM-L6-v2",
        nodes=[], edges=[],
    )
    d = sp.to_dict()
    assert d["model"] == "all-MiniLM-L6-v2"


def test_snippetpack_to_json():
    sp = SnippetPack(
        query="q", seeds=1, expanded_nodes=2, returned_nodes=1,
        hop=1, rels=["CALLS"], model="all-MiniLM-L6-v2",
        nodes=[], edges=[],
    )
    text = sp.to_json()
    assert json.loads(text)["query"] == "q"


def test_snippetpack_to_markdown_contains_query():
    sp = SnippetPack(
        query="find the thing", seeds=2, expanded_nodes=5, returned_nodes=2,
        hop=1, rels=["CONTAINS"], model="all-MiniLM-L6-v2",
        nodes=[
            {"id": "fn:mod.py:foo", "kind": "function", "name": "foo",
             "qualname": "foo", "module_path": "mod.py",
             "lineno": 1, "end_lineno": 3, "docstring": "Does foo.",
             "snippet": {"path": "mod.py", "start": 1, "end": 3,
                         "text": "    1: def foo():\n    2:     pass"}},
        ],
        edges=[],
    )
    md = sp.to_markdown()
    assert "find the thing" in md
    assert "foo" in md
    assert "```python" in md


def test_snippetpack_save_md(tmp_path):
    sp = SnippetPack(
        query="q", seeds=1, expanded_nodes=1, returned_nodes=1,
        hop=1, rels=[], model="m", nodes=[], edges=[],
    )
    out = tmp_path / "out.md"
    sp.save(out, fmt="md")
    assert out.exists()
    assert "CodeKG" in out.read_text()


def test_snippetpack_save_json(tmp_path):
    sp = SnippetPack(
        query="q", seeds=1, expanded_nodes=1, returned_nodes=1,
        hop=1, rels=[], model="m", nodes=[], edges=[],
    )
    out = tmp_path / "out.json"
    sp.save(out, fmt="json")
    assert out.exists()
    assert json.loads(out.read_text())["query"] == "q"


# ---------------------------------------------------------------------------
# Snippet utilities
# ---------------------------------------------------------------------------


def test_safe_join_valid(tmp_path):
    p = _safe_join(tmp_path, "sub/mod.py")
    assert str(p).startswith(str(tmp_path))


def test_safe_join_traversal_raises(tmp_path):
    with pytest.raises(ValueError, match="Unsafe"):
        _safe_join(tmp_path, "../../etc/passwd")


def test_compute_span_module():
    start, end = _compute_span("module", 1, 100, context=5, max_lines=50, file_nlines=200)
    assert start == 1
    assert end == 50  # capped at max_lines


def test_compute_span_function_with_ast_span():
    start, end = _compute_span("function", 10, 20, context=3, max_lines=100, file_nlines=200)
    assert start == 7   # 10 - 3
    assert end == 23    # 20 + 3


def test_compute_span_caps_at_max_lines():
    start, end = _compute_span("function", 1, 200, context=0, max_lines=50, file_nlines=300)
    assert (end - start + 1) <= 50


def test_compute_span_empty_file():
    start, end = _compute_span("function", 5, 10, context=2, max_lines=50, file_nlines=0)
    assert end < start  # sentinel for empty


def test_make_snippet_line_numbers():
    lines = ["def foo():", "    pass", ""]
    sn = _make_snippet("mod.py", lines, 1, 2)
    assert sn["path"] == "mod.py"
    assert sn["start"] == 1
    assert sn["end"] == 2
    assert "1:" in sn["text"]
    assert "2:" in sn["text"]


def test_spans_overlap_overlapping():
    assert _spans_overlap((1, 10), (8, 20)) is True


def test_spans_overlap_adjacent_within_gap():
    assert _spans_overlap((1, 5), (7, 15), gap=2) is True


def test_spans_overlap_non_overlapping():
    assert _spans_overlap((1, 5), (10, 20), gap=2) is False


def test_spans_overlap_identical():
    assert _spans_overlap((5, 10), (5, 10)) is True
