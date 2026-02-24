# CodeKG Repository Analysis Report

**Generated:** 2026-02-24 18:56:22

---

## 📊 Executive Summary

This report provides a comprehensive architectural analysis of the Python repository using CodeKG's knowledge graph. The analysis covers complexity hotspots, module coupling, critical call chains, and code quality signals to guide refactoring and architecture decisions.

---

## 📈 Baseline Metrics

| Metric | Value |
|--------|-------|
| **Total Nodes** | 3160 |
| **Total Edges** | 3602 |
| **Modules** | 1 |
| **Functions** | 211 |
| **Classes** | 17 |
| **Methods** | 83 |

### Edge Distribution

| Relationship Type | Count |
|-------------------|-------|
| CALLS | 1145 |
| CONTAINS | 311 |
| IMPORTS | 159 |
| ATTR_ACCESS | 960 |
| INHERITS | 4 |

---

## 🔥 Complexity Hotspots (High Fan-In)

Most-called functions are potential bottlenecks or core functionality. These functions are heavily depended upon across the codebase.

| # | Function | Module | Callers | Risk Level |
|---|----------|--------|---------|-----------|
| 1 | `expr_to_name()` | src/code_kg/codekg.py | **8** | 🟢 LOW |
| 2 | `_parse_expr()` | tests/test_primitives.py | **6** | 🟢 LOW |
| 3 | `to_markdown()` | src/code_kg/kg.py | **6** | 🟢 LOW |
| 4 | `_tab_snippets()` | src/code_kg/app.py | **1** | 🟢 LOW |
| 5 | `main()` | src/code_kg/codekg_snippet_packer.py | **1** | 🟢 LOW |
| 6 | `test_codekg_context_manager()` | tests/test_kg.py | **0** | 🟢 LOW |
| 7 | `test_codekg_embedder_property_lazy_init()` | tests/test_kg.py | **0** | 🟢 LOW |
| 8 | `test_codekg_index_property_lazy_init()` | tests/test_kg.py | **0** | 🟢 LOW |
| 9 | `test_codekg_node_method()` | tests/test_kg.py | **0** | 🟢 LOW |
| 10 | `test_codekg_pack_returns_snippet_pack()` | tests/test_kg.py | **0** | 🟢 LOW |
| 11 | `test_queryresult_print_summary_no_nodes()` | tests/test_kg.py | **0** | 🟢 LOW |
| 12 | `test_queryresult_print_summary_with_nodes_and_edges()` | tests/test_kg.py | **0** | 🟢 LOW |
| 13 | `test_snippetpack_to_markdown_contains_query()` | tests/test_kg.py | **0** | 🟢 LOW |
| 14 | `test_expr_to_name_attribute()` | tests/test_primitives.py | **0** | 🟢 LOW |
| 15 | `test_expr_to_name_call()` | tests/test_primitives.py | **0** | 🟢 LOW |


**Insight:** Functions with high fan-in are either core APIs or bottlenecks. Review these for:
- Thread safety and performance
- Clear documentation and contracts
- Potential for breaking changes

---

## 🔗 High Fan-Out Functions (Orchestrators)

Functions that call many others may indicate complex orchestration logic or poor separation of concerns.

✓ No extreme high fan-out functions detected. Well-balanced architecture.

---

## 📦 Module Architecture

Top modules by dependency coupling and cohesion.

| Module | Functions | Classes | Incoming | Outgoing | Cohesion |
|--------|-----------|---------|----------|----------|----------|
| `src/code_kg/codekg_snippet_packer.py` | 0 | 0 | 0 | 4 | 0.89 |

---

## 🔗 Critical Call Chains

Deepest call chains in the codebase. These represent critical execution paths.

**Chain 1** (depth: 4)

```
expr_to_name → expr_to_name → extract_repo → test_expr_to_name_simple_name
```

**Chain 2** (depth: 4)

```
_parse_expr → test_expr_to_name_simple_name → test_expr_to_name_attribute → test_expr_to_name_nested_attribute
```

**Chain 3** (depth: 4)

```
to_markdown → save → test_snippetpack_to_markdown_contains_query → test_snippetpack_to_markdown_with_edges
```

**Chain 4** (depth: 2)

```
_tab_snippets → main
```

**Chain 5** (depth: 2)

```
main → main
```

---

## 🔓 Public API Surface

Identified public APIs (module-level functions with high usage).

| Function | Module | Fan-In | Type |
|----------|--------|--------|------|
| `expr_to_name()` | src/code_kg/codekg.py | 8 | function |
| `_parse_expr()` | tests/test_primitives.py | 6 | function |


---

## ⚠️  Code Quality Issues

- ⚠️  8 orphaned functions found — consider archiving or documenting

---

## ✅ Architectural Strengths

- ✓ Well-structured with 15 core functions identified
- ✓ No god objects or god functions detected

---

## 💡 Recommendations

### Immediate Actions
1. **Review high fan-in functions** - Ensure they are documented and thread-safe
2. **Examine orchestrators** - Break down high fan-out functions into smaller components
3. **Verify public APIs** - Ensure stable contracts and clear documentation

### Medium-term Refactoring
1. **Module restructuring** - Consider reshaping modules with high coupling
2. **Dead code cleanup** - Archive or document orphaned functions
3. **Test coverage** - Add tests for critical call chains

### Long-term Architecture
1. **Layer enforcement** - Prevent unexpected module dependencies
2. **API versioning** - Manage evolution of public APIs
3. **Performance monitoring** - Track hot paths identified in this analysis

---

## 📋 Appendix: Orphaned Code

Functions with zero callers (potential dead code):

| Function | Module | Lines |
|----------|--------|-------|
| `__repr__()` | src/code_kg/kg.py | 12 |
| `__repr__()` | src/code_kg/graph.py | 11 |
| `test_codekg_embedder_property_lazy_init()` | tests/test_kg.py | 9 |
| `test_codekg_index_property_lazy_init()` | tests/test_kg.py | 7 |
| `__exit__()` | src/code_kg/kg.py | 7 |
| `__enter__()` | src/code_kg/kg.py | 6 |
| `__repr__()` | src/code_kg/store.py | 5 |
| `__init__()` | src/code_kg/store.py | 2 |


---

*Report generated by CodeKG Thorough Analysis Tool*
