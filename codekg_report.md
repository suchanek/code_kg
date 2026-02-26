> **Analysis Report Metadata**
> - **Generated:** 2026-02-26T00:31:38Z
> - **Version:** code-kg 0.3.2
> - **Commit:** c39ec4c (main)

# CodeKG Repository Analysis Report

**Generated:** 2026-02-26 00:31:38 UTC

---

## 📊 Executive Summary

This report provides a comprehensive architectural analysis of the Python repository using CodeKG's knowledge graph. The analysis covers complexity hotspots, module coupling, critical call chains, and code quality signals to guide refactoring and architecture decisions.

---

## 📈 Baseline Metrics

| Metric | Value |
|--------|-------|
| **Total Nodes** | 3607 |
| **Total Edges** | 4078 |
| **Modules** | 1 |
| **Functions** | 214 |
| **Classes** | 21 |
| **Methods** | 98 |

### Edge Distribution

| Relationship Type | Count |
|-------------------|-------|
| CALLS | 1302 |
| CONTAINS | 333 |
| IMPORTS | 171 |
| ATTR_ACCESS | 1156 |
| INHERITS | 4 |

---

## 🔥 Complexity Hotspots (High Fan-In)

Most-called functions are potential bottlenecks or core functionality. These functions are heavily depended upon across the codebase.

| # | Function | Module | Callers | Risk Level |
|---|----------|--------|---------|-----------|
| 1 | `_parse_expr()` | tests/test_primitives.py | **6** | 🟢 LOW |
| 2 | `print_summary()` | src/code_kg/codekg_thorough_analysis.py | **4** | 🟢 LOW |
| 3 | `FunctionMetrics()` | src/code_kg/codekg_thorough_analysis.py | **3** | 🟢 LOW |
| 4 | `CallChain()` | src/code_kg/codekg_thorough_analysis.py | **1** | 🟢 LOW |
| 5 | `main()` | src/code_kg/codekg_snippet_packer.py | **1** | 🟢 LOW |
| 6 | `_analyze_dependencies()` | src/code_kg/codekg_thorough_analysis.py | **1** | 🟢 LOW |
| 7 | `_analyze_fan_in()` | src/code_kg/codekg_thorough_analysis.py | **1** | 🟢 LOW |
| 8 | `_analyze_fan_out()` | src/code_kg/codekg_thorough_analysis.py | **1** | 🟢 LOW |
| 9 | `_compile_results()` | src/code_kg/codekg_thorough_analysis.py | **1** | 🟢 LOW |
| 10 | `_identify_public_apis()` | src/code_kg/codekg_thorough_analysis.py | **1** | 🟢 LOW |
| 11 | `run_analysis()` | src/code_kg/codekg_thorough_analysis.py | **1** | 🟢 LOW |
| 12 | `test_codekg_embedder_property_lazy_init()` | tests/test_kg.py | **0** | 🟢 LOW |
| 13 | `test_codekg_index_property_lazy_init()` | tests/test_kg.py | **0** | 🟢 LOW |
| 14 | `test_codekg_node_method()` | tests/test_kg.py | **0** | 🟢 LOW |
| 15 | `test_codekg_pack_returns_snippet_pack()` | tests/test_kg.py | **0** | 🟢 LOW |


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
_parse_expr → test_expr_to_name_simple_name → test_expr_to_name_attribute → test_expr_to_name_nested_attribute
```

**Chain 2** (depth: 4)

```
print_summary → test_queryresult_print_summary_no_nodes → test_queryresult_print_summary_with_nodes_and_edges → main
```

**Chain 3** (depth: 4)

```
FunctionMetrics → _analyze_fan_in → _analyze_fan_out → _analyze_dependencies
```

**Chain 4** (depth: 2)

```
CallChain → _analyze_critical_paths
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
| `_parse_expr()` | tests/test_primitives.py | 6 | function |


---

## ⚠️  Code Quality Issues

- ⚠️  5 orphaned functions found — consider archiving or documenting

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
| `cli()` | src/code_kg/codekg_thorough_analysis.py | 69 |
| `__init__()` | src/code_kg/codekg_thorough_analysis.py | 17 |
| `test_codekg_embedder_property_lazy_init()` | tests/test_kg.py | 9 |
| `__enter__()` | src/code_kg/kg.py | 6 |
| `__repr__()` | src/code_kg/store.py | 5 |


---

*Report generated by CodeKG Thorough Analysis Tool*
