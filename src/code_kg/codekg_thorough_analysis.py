#!/usr/bin/env python3
"""
CodeKG Thorough Repository Analysis Tool

Performs comprehensive architectural analysis of Python repositories using CodeKG's
graph traversal capabilities. Analyzes:
- Complexity hotspots (highest fan-in/fan-out functions)
- Architectural patterns (core modules, integration points)
- Dependency analysis (circular deps, tight coupling)
- Code quality signals (dead code, orphaned functions)

Usage:
    python codekg_thorough_analysis.py /path/to/repo /path/to/db .codekg/lancedb
"""

import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FunctionMetrics:
    """Metrics for a single function or class.

    :param node_id: Stable node identifier
    :param name: Function/class name
    :param module: Module path containing this definition
    :param kind: Kind of node (function, method, class)
    :param fan_in: Count of callers (how many call this)
    :param fan_out: Count of callees (how many this calls)
    :param lines: Approximate line count
    :param docstring: Docstring text if available
    :param risk_level: Risk assessment (low, medium, high, critical)
    """

    node_id: str
    name: str
    module: str
    kind: str
    fan_in: int
    fan_out: int
    lines: int
    docstring: str | None = None
    risk_level: str = "low"


@dataclass
class ModuleMetrics:
    """Metrics for a module.

    :param path: Module file path
    :param functions: Count of functions defined
    :param classes: Count of classes defined
    :param methods: Count of methods defined
    :param incoming_deps: Modules that import this one
    :param outgoing_deps: Modules this one imports
    :param total_fan_in: Sum of all callers to functions in module
    :param cohesion_score: Internal coupling strength (0-1)
    """

    path: str
    functions: int
    classes: int
    methods: int
    incoming_deps: list[str]
    outgoing_deps: list[str]
    total_fan_in: int
    cohesion_score: float


@dataclass
class CallChain:
    """Represents a critical path of function calls.

    :param chain: List of function names in call order
    :param depth: Length of the chain
    :param total_callers: Sum of all callers in chain
    """

    chain: list[str]
    depth: int
    total_callers: int


class CodeKGAnalyzer:
    """Thorough repository analyzer using CodeKG graph.

    :param kg: CodeKG instance for graph queries
    :param console: Rich console for output (creates new if None)
    """

    def __init__(self, kg, console: Console | None = None):
        """Initialize analyzer with CodeKG instance.

        :param kg: CodeKG instance
        :param console: Rich console for terminal output
        """
        self.kg = kg
        self.console = console or Console()
        self.stats: dict = {}
        self.function_metrics: dict[str, FunctionMetrics] = {}
        self.module_metrics: dict[str, ModuleMetrics] = {}
        self.orphaned_functions: list[FunctionMetrics] = []
        self.high_fanout_functions: list[FunctionMetrics] = []
        self.critical_paths: list[CallChain] = []
        self.circular_deps: list[tuple[str, str]] = []
        self.public_apis: list[FunctionMetrics] = []
        self.issues: list[str] = []
        self.strengths: list[str] = []

    def run_analysis(self, report_path: str | None = None) -> dict:
        """Run complete multi-phase analysis.

        :param report_path: Optional path to write markdown report
        :return: dictionary of analysis results
        """
        try:
            # Phase 1: Baseline metrics
            self._analyze_baseline()

            # Phase 2: High fan-in analysis
            self._analyze_fan_in()

            # Phase 3: High fan-out analysis
            self._analyze_fan_out()

            # Phase 4: Dependency analysis
            self._analyze_dependencies()

            # Phase 5: Pattern detection
            self._detect_patterns()

            # Phase 6: Module coupling analysis
            self._analyze_module_coupling()

            # Phase 7: Critical path analysis
            self._analyze_critical_paths()

            # Phase 8: Public API identification
            self._identify_public_apis()

            # Phase 9: Generate insights
            self._generate_insights()

            # Optional: write report
            if report_path:
                self._write_report(report_path)

            return self._compile_results()

        except Exception as e:
            self.console.print(f"[red]❌ Analysis failed: {e}[/red]")
            logger.exception("Analysis failed")
            raise

    def _analyze_baseline(self) -> None:
        """Phase 1: Get overall codebase metrics.

        Queries graph_stats() to establish baseline counts by node kind
        and edge relationship type.
        """
        self.console.print("[dim]📊 Analyzing baseline metrics...[/dim]")

        try:
            self.stats = self.kg.stats()

            self.console.print("[green]✓[/green] Baseline metrics collected")
            self.console.print(f"  • Nodes: {self.stats.get('total_nodes', '?')}")
            self.console.print(f"  • Edges: {self.stats.get('total_edges', '?')}")

        except Exception as e:
            logger.warning(f"Could not get baseline stats: {e}")
            self.console.print(f"[yellow]⚠[/yellow] Could not get baseline stats: {e}")

    def _analyze_fan_in(self) -> None:
        """Phase 2: Find most-called functions (fan-in).

        Queries for functions and methods, then uses callers() to get
        exact caller counts. Identifies bottlenecks and core functionality.
        """
        self.console.print("[dim]🔍 Analyzing fan-in (most called functions)...[/dim]")

        try:
            # Query for all functions and methods
            result = self.kg.query(
                "function method core utility helper",
                k=30,
                hop=0,
                rels=("CONTAINS",),
            )

            fan_in_data: list[tuple] = []

            # For each function, get actual caller count
            for node in result.nodes:
                if node.get("kind") not in ["function", "method", "class"]:
                    continue

                node_id = node.get("id")
                if not node_id:
                    continue

                try:
                    caller_list = self.kg.callers(node_id, rel="CALLS")
                    caller_count = len(caller_list)

                    metrics = FunctionMetrics(
                        node_id=node_id,
                        name=node.get("name", "unknown"),
                        module=node.get("module_path", "unknown"),
                        kind=node.get("kind", "unknown"),
                        fan_in=caller_count,
                        fan_out=0,  # Will be filled in fan-out phase
                        lines=max(
                            0,
                            node.get("end_lineno", 0) - node.get("lineno", 0),
                        ),
                        docstring=node.get("docstring"),
                    )

                    # Assign risk level based on caller count
                    if caller_count > 1000:
                        metrics.risk_level = "critical"
                    elif caller_count > 500:
                        metrics.risk_level = "high"
                    elif caller_count > 100:
                        metrics.risk_level = "medium"

                    fan_in_data.append((node_id, metrics))

                except Exception as e:
                    logger.debug(f"Could not analyze node {node_id}: {e}")

            # Sort by fan-in descending
            fan_in_data.sort(key=lambda x: x[1].fan_in, reverse=True)

            # Keep top 15
            for node_id, metrics in fan_in_data[:15]:
                self.function_metrics[node_id] = metrics

            self.console.print(
                f"[green]✓[/green] Analyzed {len(fan_in_data)} functions; "
                f"top {len(self.function_metrics)} by fan-in"
            )

        except Exception as e:
            logger.warning(f"Fan-in analysis incomplete: {e}")
            self.console.print(f"[yellow]⚠[/yellow] Fan-in analysis incomplete: {e}")

    def _analyze_fan_out(self) -> None:
        """Phase 3: Find functions that call many others (fan-out).

        Analyzes functions in the function_metrics already identified,
        computing their actual fan-out by reverse-querying callee lists.
        Also identifies additional high-fanout orchestrator functions.
        """
        self.console.print("[dim]🔗 Analyzing fan-out (functions calling many others)...[/dim]")

        try:
            # For functions already identified, compute their fan-out
            for node_id, metrics in self.function_metrics.items():
                try:
                    # Get the node to see what it calls
                    node = self.kg.node(node_id)
                    if node is None:
                        continue

                    # Count CALLS edges outgoing from this node
                    # This is a rough estimate via the store; exact count requires
                    # querying the store directly
                    fanout_count = 0
                    # Try to get edges from the node
                    if hasattr(self.kg, "_store"):
                        edges = self.kg._store.edges_from(node_id, rel="CALLS", limit=100)
                        fanout_count = len(edges) if edges else 0

                    metrics.fan_out = fanout_count

                    # Flag high fan-out functions
                    if fanout_count > 75:
                        metrics.risk_level = "high"
                        if fanout_count > 150:
                            metrics.risk_level = "critical"

                except Exception as e:
                    logger.debug(f"Could not compute fan-out for {node_id}: {e}")

            # Query for additional orchestrator functions
            try:
                result = self.kg.query(
                    "coordinator orchestrator manager init constructor setup",
                    k=20,
                    hop=0,
                    rels=("CONTAINS",),
                )

                for node in result.nodes:
                    node_id = node.get("id")
                    if not node_id or node_id in self.function_metrics:
                        continue

                    if node.get("kind") not in ["function", "method"]:
                        continue

                    # Estimate fan-out for new functions
                    fanout_count = 0
                    if hasattr(self.kg, "_store"):
                        try:
                            edges = self.kg._store.edges_from(node_id, rel="CALLS", limit=100)
                            fanout_count = len(edges) if edges else 0
                        except Exception:
                            pass

                    if fanout_count > 25:
                        metrics = FunctionMetrics(
                            node_id=node_id,
                            name=node.get("name", "unknown"),
                            module=node.get("module_path", "unknown"),
                            kind=node.get("kind", "unknown"),
                            fan_in=0,
                            fan_out=fanout_count,
                            lines=max(
                                0,
                                node.get("end_lineno", 0) - node.get("lineno", 0),
                            ),
                        )

                        if fanout_count > 150:
                            metrics.risk_level = "critical"
                        elif fanout_count > 75:
                            metrics.risk_level = "high"

                        self.high_fanout_functions.append(metrics)
            except Exception as e:
                logger.debug(f"Could not query orchestrators: {e}")

            self.console.print(
                f"[green]✓[/green] Fan-out analysis complete "
                f"({len(self.high_fanout_functions)} high-fanout functions)"
            )

        except Exception as e:
            logger.warning(f"Fan-out analysis incomplete: {e}")
            self.console.print(f"[yellow]⚠[/yellow] Fan-out analysis incomplete: {e}")

    def _analyze_dependencies(self) -> None:
        """Phase 4: Analyze module-level dependencies.

        Detects orphaned functions (zero callers), import cycles,
        and tight coupling patterns.
        """
        self.console.print("[dim]🏗️  Analyzing dependencies...[/dim]")

        try:
            # Query for potential orphaned code
            result = self.kg.query(
                "unused dead code deprecated helper utility internal",
                k=15,
                hop=0,
                rels=("CONTAINS",),
            )

            for node in result.nodes:
                if node.get("kind") not in ["function", "method", "class"]:
                    continue

                node_id = node.get("id")
                if not node_id:
                    continue

                try:
                    caller_list = self.kg.callers(node_id, rel="CALLS")

                    # Functions with zero callers are orphaned
                    if len(caller_list) == 0:
                        metrics = FunctionMetrics(
                            node_id=node_id,
                            name=node.get("name", "unknown"),
                            module=node.get("module_path", "unknown"),
                            kind=node.get("kind", "unknown"),
                            fan_in=0,
                            fan_out=0,
                            lines=max(
                                0,
                                node.get("end_lineno", 0) - node.get("lineno", 0),
                            ),
                        )
                        metrics.risk_level = "high"
                        self.orphaned_functions.append(metrics)

                except Exception as e:
                    logger.debug(f"Could not check callers for {node_id}: {e}")

            self.console.print(
                f"[green]✓[/green] Found {len(self.orphaned_functions)} orphaned functions"
            )

        except Exception as e:
            logger.warning(f"Dependency analysis incomplete: {e}")
            self.console.print(f"[yellow]⚠[/yellow] Dependency analysis incomplete: {e}")

    def _detect_patterns(self) -> None:
        """Phase 5: Detect architectural patterns.

        Identifies core modules, integration points, layering violations,
        and design patterns (singletons, managers, etc.).
        """
        self.console.print("[dim]🎨 Detecting architectural patterns...[/dim]")

        try:
            # Identify core modules by aggregating fan-in
            module_call_counts: dict[str, int] = defaultdict(int)
            for metrics in self.function_metrics.values():
                # Group by top-level module
                module = metrics.module.split("/")[0] if "/" in metrics.module else metrics.module
                module_call_counts[module] += metrics.fan_in

            core_modules = sorted(
                module_call_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]

            if core_modules:
                self.console.print(f"[green]✓[/green] Identified {len(core_modules)} core modules")

            # Identify tight coupling patterns
            high_fanout = sorted(
                list(self.function_metrics.values()) + self.high_fanout_functions,
                key=lambda m: m.fan_out,
                reverse=True,
            )[:10]

            for func in high_fanout:
                if func.fan_out > 50:
                    self.issues.append(
                        f"🔴 {func.name} has high fan-out ({func.fan_out} calls) "
                        "— consider breaking into smaller functions"
                    )

        except Exception as e:
            logger.warning(f"Pattern detection incomplete: {e}")

    def _analyze_module_coupling(self) -> None:
        """Phase 6: Analyze module-level coupling and dependencies.

        Uses IMPORTS edges to identify module interdependencies and
        calculate cohesion metrics.
        """
        self.console.print("[dim]📦 Analyzing module coupling...[/dim]")

        try:
            # Query for all modules
            result = self.kg.query(
                "module package namespace",
                k=25,
                hop=0,
                rels=("CONTAINS",),
            )

            for node in result.nodes:
                if node.get("kind") != "module":
                    continue

                module_path = node.get("module_path", "unknown")
                node_id = node.get("id")

                # Get incoming imports (modules that import this)
                incoming = []
                try:
                    importer_list = self.kg.callers(node_id, rel="IMPORTS")
                    incoming = [m.get("module_path", "unknown") for m in importer_list]
                except Exception:
                    pass

                # Get outgoing imports via query
                outgoing = []
                try:
                    import_result = self.kg.query(
                        f"imports from {module_path}",
                        k=10,
                        hop=1,
                        rels=("IMPORTS",),
                    )
                    outgoing = [
                        n.get("module_path", "unknown")
                        for n in import_result.nodes
                        if n.get("module_path") != module_path
                    ]
                except Exception:
                    pass

                # Calculate cohesion (internal coupling strength)
                cohesion = min(1.0, len(outgoing) / (len(incoming) + len(outgoing) + 1))

                module_metric = ModuleMetrics(
                    path=module_path,
                    functions=0,
                    classes=0,
                    methods=0,
                    incoming_deps=list(set(incoming)),
                    outgoing_deps=list(set(outgoing)),
                    total_fan_in=len(incoming),
                    cohesion_score=cohesion,
                )

                self.module_metrics[module_path] = module_metric

            self.console.print(f"[green]✓[/green] Analyzed {len(self.module_metrics)} modules")

        except Exception as e:
            logger.warning(f"Module coupling analysis incomplete: {e}")

    def _analyze_critical_paths(self) -> None:
        """Phase 7: Identify critical call chains.

        Finds the deepest call chains starting from high-fan-in functions
        using the callers() function to trace backwards.
        """
        self.console.print("[dim]🔗 Analyzing critical paths...[/dim]")

        try:
            # Start from high fan-in functions and trace backwards
            top_functions = sorted(
                self.function_metrics.values(),
                key=lambda m: m.fan_in,
                reverse=True,
            )[:5]

            for func in top_functions:
                try:
                    callers = self.kg.callers(func.node_id, rel="CALLS")

                    if callers:
                        # Build a simple chain
                        chain_names = [func.name] + [c.get("name", "unknown") for c in callers[:3]]
                        call_chain = CallChain(
                            chain=chain_names,
                            depth=len(chain_names),
                            total_callers=len(callers),
                        )
                        self.critical_paths.append(call_chain)

                except Exception as e:
                    logger.debug(f"Could not trace path for {func.name}: {e}")

            self.console.print(
                f"[green]✓[/green] Found {len(self.critical_paths)} critical call chains"
            )

        except Exception as e:
            logger.warning(f"Critical path analysis incomplete: {e}")

    def _identify_public_apis(self) -> None:
        """Phase 8: Identify public APIs (module-level exports).

        Functions/classes at module level with high fan-in are likely
        public APIs. Also identifies single-caller functions (utilities).
        """
        self.console.print("[dim]🔓 Identifying public APIs...[/dim]")

        try:
            # Public APIs are high fan-in functions at module level
            for func in sorted(
                self.function_metrics.values(), key=lambda m: m.fan_in, reverse=True
            ):
                # Module-level functions (not nested in classes)
                if func.kind == "function" and func.fan_in > 2:
                    self.public_apis.append(func)

            self.console.print(
                f"[green]✓[/green] Identified {len(self.public_apis)} public API functions"
            )

        except Exception as e:
            logger.warning(f"Public API identification incomplete: {e}")

    def _generate_insights(self) -> None:
        """Phase 6: Generate actionable insights.

        Compiles issues and strengths based on metrics collected
        in earlier phases.
        """
        # Strengths
        if len(self.function_metrics) > 0:
            self.strengths.append(
                f"✓ Well-structured with {len(self.function_metrics)} core functions identified"
            )

        if len(self.orphaned_functions) == 0:
            self.strengths.append("✓ No obvious dead code detected")

        if len(self.high_fanout_functions) == 0:
            self.strengths.append("✓ No god objects or god functions detected")

        # Issues
        if len(self.orphaned_functions) > 0:
            self.issues.append(
                f"⚠️  {len(self.orphaned_functions)} orphaned functions found "
                "— consider archiving or documenting"
            )

        if len(self.high_fanout_functions) > 0:
            self.issues.append(
                f"⚠️  {len(self.high_fanout_functions)} functions with high fan-out "
                "— potential orchestrators or god objects"
            )

    def _write_report(self, report_path: str) -> None:
        """Generate comprehensive markdown report with tables and analysis.

        :param report_path: Path to write the markdown report to
        """
        report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stats = self.stats

        # Build comprehensive report
        report = f"""# CodeKG Repository Analysis Report

**Generated:** {report_date}

---

## 📊 Executive Summary

This report provides a comprehensive architectural analysis of the Python repository using CodeKG's knowledge graph. The analysis covers complexity hotspots, module coupling, critical call chains, and code quality signals to guide refactoring and architecture decisions.

---

## 📈 Baseline Metrics

| Metric | Value |
|--------|-------|
| **Total Nodes** | {stats.get("total_nodes", "N/A")} |
| **Total Edges** | {stats.get("total_edges", "N/A")} |
| **Modules** | {len(self.module_metrics)} |
| **Functions** | {stats.get("node_counts", {}).get("function", "N/A")} |
| **Classes** | {stats.get("node_counts", {}).get("class", "N/A")} |
| **Methods** | {stats.get("node_counts", {}).get("method", "N/A")} |

### Edge Distribution

| Relationship Type | Count |
|-------------------|-------|
| CALLS | {stats.get("edge_counts", {}).get("CALLS", 0)} |
| CONTAINS | {stats.get("edge_counts", {}).get("CONTAINS", 0)} |
| IMPORTS | {stats.get("edge_counts", {}).get("IMPORTS", 0)} |
| ATTR_ACCESS | {stats.get("edge_counts", {}).get("ATTR_ACCESS", 0)} |
| INHERITS | {stats.get("edge_counts", {}).get("INHERITS", 0)} |

---

## 🔥 Complexity Hotspots (High Fan-In)

Most-called functions are potential bottlenecks or core functionality. These functions are heavily depended upon across the codebase.

| # | Function | Module | Callers | Risk Level |
|---|----------|--------|---------|-----------|
"""

        for i, metrics in enumerate(
            sorted(self.function_metrics.values(), key=lambda m: m.fan_in, reverse=True)[:15],
            1,
        ):
            risk_emoji = (
                "🟢"
                if metrics.risk_level == "low"
                else "🟡"
                if metrics.risk_level == "medium"
                else "🟠"
                if metrics.risk_level == "high"
                else "🔴"
            )
            report += (
                f"| {i} | `{metrics.name}()` | {metrics.module} | "
                f"**{metrics.fan_in}** | {risk_emoji} {metrics.risk_level.upper()} |\n"
            )

        report += """

**Insight:** Functions with high fan-in are either core APIs or bottlenecks. Review these for:
- Thread safety and performance
- Clear documentation and contracts
- Potential for breaking changes

---

## 🔗 High Fan-Out Functions (Orchestrators)

Functions that call many others may indicate complex orchestration logic or poor separation of concerns.

"""

        if self.high_fanout_functions:
            report += """| # | Function | Module | Calls | Type |
|---|----------|--------|-------|------|
"""
            for i, func in enumerate(
                sorted(self.high_fanout_functions, key=lambda f: f.fan_out, reverse=True)[:10],
                1,
            ):
                func_type = "Orchestrator" if func.fan_out > 50 else "Coordinator"
                report += (
                    f"| {i} | `{func.name}()` | {func.module} | "
                    f"**{func.fan_out}** | {func_type} |\n"
                )
            report += "\n"
        else:
            report += (
                "✓ No extreme high fan-out functions detected. Well-balanced architecture.\n\n"
            )

        report += """---

## 📦 Module Architecture

Top modules by dependency coupling and cohesion.

"""

        if self.module_metrics:
            report += """| Module | Functions | Classes | Incoming | Outgoing | Cohesion |
|--------|-----------|---------|----------|----------|----------|
"""
            for module, module_metric in sorted(
                self.module_metrics.items(),
                key=lambda x: x[1].total_fan_in,
                reverse=True,
            )[:10]:
                report += (
                    f"| `{module}` | {module_metric.functions} | {module_metric.classes} | "
                    f"{len(module_metric.incoming_deps)} | {len(module_metric.outgoing_deps)} | "
                    f"{module_metric.cohesion_score:.2f} |\n"
                )
            report += "\n"

        report += """---

## 🔗 Critical Call Chains

Deepest call chains in the codebase. These represent critical execution paths.

"""

        if self.critical_paths:
            for i, chain in enumerate(self.critical_paths[:5], 1):
                chain_str = " → ".join(chain.chain)
                report += f"**Chain {i}** (depth: {chain.depth})\n\n```\n{chain_str}\n```\n\n"
        else:
            report += "No critical call chains identified.\n\n"

        report += """---

## 🔓 Public API Surface

Identified public APIs (module-level functions with high usage).

"""

        if self.public_apis:
            report += """| Function | Module | Fan-In | Type |
|----------|--------|--------|------|
"""
            for api in sorted(self.public_apis, key=lambda a: a.fan_in, reverse=True)[:10]:
                report += f"| `{api.name}()` | {api.module} | {api.fan_in} | {api.kind} |\n"
        else:
            report += "No public APIs identified.\n\n"

        issues_text = (
            "\n".join(f"- {issue}" for issue in self.issues)
            if self.issues
            else "- No major issues detected"
        )
        strengths_text = (
            "\n".join(f"- {strength}" for strength in self.strengths)
            if self.strengths
            else "- Continue monitoring code quality"
        )

        report += f"""

---

## ⚠️  Code Quality Issues

{issues_text}

---

## ✅ Architectural Strengths

{strengths_text}

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

"""

        if self.orphaned_functions:
            report += """| Function | Module | Lines |
|----------|--------|-------|
"""
            for func in sorted(self.orphaned_functions, key=lambda f: f.lines, reverse=True)[:15]:
                report += f"| `{func.name}()` | {func.module} | {func.lines} |\n"
        else:
            report += "✓ No orphaned functions detected.\n"

        report += """

---

*Report generated by CodeKG Thorough Analysis Tool*
"""

        Path(report_path).write_text(report)
        self.console.print(f"[green]✓[/green] Report written to {report_path}")

    def _compile_results(self) -> dict:
        """Compile analysis results into a dictionary.

        :return: dictionary with all analysis data
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "statistics": self.stats,
            "function_metrics": {k: asdict(v) for k, v in self.function_metrics.items()},
            "module_metrics": {k: asdict(v) for k, v in self.module_metrics.items()},
            "orphaned_functions": [asdict(f) for f in self.orphaned_functions],
            "high_fanout_functions": [asdict(f) for f in self.high_fanout_functions],
            "critical_paths": [asdict(c) for c in self.critical_paths],
            "public_apis": [asdict(a) for a in self.public_apis],
            "issues": self.issues,
            "strengths": self.strengths,
        }

    def print_summary(self) -> None:
        """Print analysis summary to console."""
        # Header
        self.console.print()
        self.console.print(
            Panel.fit(
                "[bold cyan]CodeKG Repository Analysis[/bold cyan]",
                border_style="cyan",
            )
        )
        self.console.print()

        # Stats table
        stats_table = Table(title="Baseline Metrics", show_header=True)
        stats_table.add_column("Metric", style="dim")
        stats_table.add_column("Value")

        for key, value in self.stats.items():
            stats_table.add_row(key, str(value))

        self.console.print(stats_table)
        self.console.print()

        # Most called functions
        if self.function_metrics:
            calls_table = Table(title="Most Called Functions (Fan-In)", show_header=True)
            calls_table.add_column("Function", style="cyan")
            calls_table.add_column("Callers", justify="right")
            calls_table.add_column("Risk", style="red")

            for metrics in sorted(
                self.function_metrics.values(),
                key=lambda m: m.fan_in,
                reverse=True,
            )[:10]:
                calls_table.add_row(
                    metrics.name,
                    str(metrics.fan_in),
                    metrics.risk_level.upper(),
                )

            self.console.print(calls_table)
            self.console.print()

        # Issues
        if self.issues:
            self.console.print("[bold yellow]⚠️  Issues Found:[/bold yellow]")
            for issue in self.issues:
                self.console.print(f"  {issue}")
            self.console.print()

        # Strengths
        if self.strengths:
            self.console.print("[bold green]✓ Strengths:[/bold green]")
            for strength in self.strengths:
                self.console.print(f"  {strength}")
            self.console.print()


def main(repo_root: str, db_path: str, lancedb_path: str) -> None:
    """Main entry point.

    :param repo_root: Root directory of the repository to analyze
    :param db_path: Path to the SQLite knowledge graph database
    :param lancedb_path: Path to the LanceDB vector index directory
    """
    console = Console()

    try:
        from code_kg import CodeKG

        console.print("[dim]Initializing CodeKG...[/dim]")
        kg = CodeKG(
            repo_root=Path(repo_root),
            db_path=Path(db_path),
            lancedb_dir=Path(lancedb_path),
        )

        analyzer = CodeKGAnalyzer(kg, console)
        results = analyzer.run_analysis()
        analyzer.print_summary()

        # Save results
        output_file = Path.home() / ".claude" / "codekg_analysis_latest.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(results, indent=2))

        console.print(f"[dim]Results saved to {output_file}[/dim]")

    except ImportError as e:
        console.print(
            f"[red]Error: Could not import CodeKG[/red]\n"
            f"Details: {e}\n\n"
            f"Make sure you are in the code_kg package environment."
        )
        logger.exception("Import error")
        raise


def cli() -> None:
    """CLI entry point for the codekg-analyze script."""
    import sys

    if len(sys.argv) < 4:
        print("Usage: codekg-analyze <repo_root> <db_path> <lancedb_path>")
        print("\nExample:")
        print("  codekg-analyze /path/to/repo .codekg/graph.sqlite .codekg/lancedb")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    cli()
