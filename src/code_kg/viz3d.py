#!/usr/bin/env python3
"""
viz3d.py — PyVista/PyQt5 3-D knowledge-graph visualiser for CodeKG.

Reads nodes and edges from :class:`~code_kg.store.GraphStore` (SQLite),
computes a 3-D layout via a pluggable :class:`~code_kg.layout3d.Layout3D`
strategy, and renders an interactive scene using PyVista and PyQt5.

Node shapes and colours follow the same vocabulary as the Streamlit
``app.py`` visualiser (pyvis), ensuring visual consistency across views.

Click any node to print its metadata and docstring to the console.

Usage::

    from code_kg.viz3d import KGViz3D
    from code_kg.layout3d import AlliumLayout

    viz = KGViz3D(".codekg/graph.sqlite", layout=AlliumLayout())
    viz.build()
    viz.show()

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Colour / shape vocabulary  (aligned with app.py)
# ---------------------------------------------------------------------------

_KIND_COLOR: Dict[str, str] = {
    "module": "#4A90D9",    # blue
    "class": "#E67E22",     # orange
    "function": "#27AE60",  # green
    "method": "#8E44AD",    # purple
    "symbol": "#95A5A6",    # grey
}

_REL_COLOR: Dict[str, str] = {
    "CONTAINS": "#BDC3C7",  # light grey
    "CALLS": "#E74C3C",     # red
    "IMPORTS": "#3498DB",   # blue
    "INHERITS": "#F39C12",  # amber
}

# Node radius per kind
_KIND_SIZE: Dict[str, float] = {
    "module": 0.60,
    "class": 0.45,
    "function": 0.35,
    "method": 0.25,
    "symbol": 0.20,
}

# LOD tier thresholds (total node count)
_LOD_HIGH = 400    # ≤ this: rich geometry (icospheres, cylinders)
_LOD_LOW = 1500    # ≤ this: cubes; above: small spheres only


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    """Convert a ``#RRGGBB`` hex string to an (r, g, b) float tuple in [0, 1].

    :param hex_color: Hex colour string, e.g. ``"#E74C3C"``.
    :return: ``(r, g, b)`` tuple with components in 0–1.
    """
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _arc_points(
    p1: np.ndarray,
    p2: np.ndarray,
    n_pts: int = 24,
    lift_factor: float = 0.35,
) -> np.ndarray:
    """
    Generate points along a quadratic Bézier arc between *p1* and *p2*.

    The arc apex is lifted above the straight line by
    ``lift_factor × |p2 − p1|`` in the Z direction, so edges arc visibly
    above the node layer and never clip through geometry.

    :param p1: Start point (3-D).
    :param p2: End point (3-D).
    :param n_pts: Number of sample points along the arc.
    :param lift_factor: Fraction of chord length used as Z lift at the apex.
    :return: ``(n_pts, 3)`` float array of arc sample points.
    """
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    mid = (p1 + p2) / 2.0
    chord = np.linalg.norm(p2 - p1)
    mid[2] += lift_factor * chord  # lift apex upward in Z

    t = np.linspace(0.0, 1.0, n_pts)[:, None]
    # Quadratic Bézier: B(t) = (1-t)² p1 + 2t(1-t) mid + t² p2
    return (1 - t) ** 2 * p1 + 2 * t * (1 - t) * mid + t**2 * p2


def _format_docstring(docstring: str | None) -> str:
    """
    Strip ``:param:``-style annotations from a docstring for console display.

    :param docstring: Raw Python docstring, or ``None``.
    :return: Human-readable plain-text string.
    """
    if not docstring:
        return "(no docstring)"
    lines = docstring.strip().splitlines()
    cleaned: List[str] = []
    for line in lines:
        line = line.strip()
        if re.match(r":type\b|:rtype\b", line):
            continue
        line = re.sub(r":param (\w+):", r"  \1:", line)
        line = re.sub(r":return:", "  →", line)
        cleaned.append(line)
    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# KGViz3D — main renderer class
# ---------------------------------------------------------------------------


class KGViz3D:
    """
    Interactive 3-D knowledge-graph visualiser powered by PyVista and PyQt5.

    Reads the graph from a :class:`~code_kg.store.GraphStore` SQLite file,
    computes positions via a pluggable :class:`~code_kg.layout3d.Layout3D`
    strategy, and renders nodes and cross-cutting edges in an interactive
    PyVista window with eye-dome lighting.

    **Node shapes** (LOD-adaptive):

    - ``module`` → cube
    - ``class`` → icosphere
    - ``function`` → cylinder
    - ``method`` → small icosphere
    - ``symbol`` → tiny sphere

    **Edge rendering**:

    - ``CONTAINS`` → thin grey lines (opt-in via *show_contains*)
    - ``CALLS`` → red Bézier arc
    - ``IMPORTS`` → blue Bézier arc
    - ``INHERITS`` → amber Bézier arc

    Click anywhere in the scene to identify and describe the nearest node
    in the console.

    :param db_path: Path to the ``.codekg/graph.sqlite`` SQLite database.
    :param layout: Layout strategy; defaults to
        :class:`~code_kg.layout3d.AlliumLayout`.
    :param rel_filter: Set of edge relation types to render as arcs.
        Defaults to ``{"CALLS", "IMPORTS", "INHERITS"}``.
    :param show_contains: Render ``CONTAINS`` edges as thin grey lines.
    """

    def __init__(
        self,
        db_path: str | Path,
        layout=None,
        rel_filter: Optional[Set[str]] = None,
        show_contains: bool = False,
    ) -> None:
        """Initialise the visualiser.

        :param db_path: Path to the SQLite database file.
        :param layout: :class:`~code_kg.layout3d.Layout3D` instance.
        :param rel_filter: Which non-CONTAINS relation types to render as arcs.
        :param show_contains: Whether to render CONTAINS edges.
        """
        from code_kg.layout3d import AlliumLayout

        self.db_path = Path(db_path)
        self.layout = layout or AlliumLayout()
        self.rel_filter: Set[str] = rel_filter or {"CALLS", "IMPORTS", "INHERITS"}
        self.show_contains = show_contains

        self._nodes: List = []
        self._edges: List = []
        self._positions: Dict[str, np.ndarray] = {}
        self._id_to_doc: Dict[str, str] = {}
        self._plotter = None
        self._lod: str = "high"

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_graph(self) -> None:
        """Load all nodes and edges from the SQLite store.

        Populates ``self._nodes`` and ``self._edges`` as
        :class:`~code_kg.layout3d.LayoutNode` /
        :class:`~code_kg.layout3d.LayoutEdge` instances.
        """
        from code_kg.layout3d import LayoutEdge, LayoutNode
        from code_kg.store import GraphStore

        with GraphStore(self.db_path) as store:
            raw_nodes = store.query_nodes()
            node_ids = {n["id"] for n in raw_nodes}
            raw_edges = store.edges_within(node_ids)

        self._nodes = [LayoutNode.from_dict(n) for n in raw_nodes]
        self._edges = [LayoutEdge.from_dict(e) for e in raw_edges]
        self._id_to_doc = {
            n.id: _format_docstring(n.docstring) for n in self._nodes
        }

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> KGViz3D:
        """
        Load the graph, compute the 3-D layout, and render the scene.

        :return: ``self`` (for method chaining).
        :raises ImportError: If PyVista / pyvistaqt are not installed.
        """
        try:
            import pyvista as pv
            from pyvistaqt import BackgroundPlotter
        except ImportError as exc:
            raise ImportError(
                "PyVista dependencies not installed. "
                "Run: poetry install --extras viz3d"
            ) from exc

        self._load_graph()
        n_total = len(self._nodes)
        print(f"[codekg-viz3d] {n_total} nodes, {len(self._edges)} edges")
        print(f"[codekg-viz3d] layout : {type(self.layout).__name__}")

        self._positions = self.layout.compute(self._nodes, self._edges)

        # Select LOD tier
        if n_total <= _LOD_HIGH:
            self._lod = "high"
        elif n_total <= _LOD_LOW:
            self._lod = "low"
        else:
            self._lod = "points"
        print(f"[codekg-viz3d] LOD    : {self._lod} ({n_total} nodes)")

        pv.set_plot_theme("dark")
        self._plotter = BackgroundPlotter(title="CodeKG 3D — " + self.db_path.name)
        self._plotter.enable_eye_dome_lighting()

        self._render_nodes()
        self._render_edges()

        self._plotter.enable_point_picking(
            callback=self._on_pick,
            show_message=False,
            use_mesh=False,
        )
        self._plotter.add_axes()
        self._plotter.reset_camera()
        return self

    # ------------------------------------------------------------------
    # Node rendering
    # ------------------------------------------------------------------

    def _node_mesh(self, kind: str, center: np.ndarray, size: float):
        """
        Return a PyVista mesh for a node, adapting geometry to the LOD tier.

        - ``"high"`` LOD: cubes (modules), cylinders (functions),
          icospheres (classes/methods/symbols).
        - ``"low"`` LOD: cubes for all kinds.
        - ``"points"`` LOD: minimal spheres.

        :param kind: Node kind string.
        :param center: 3-D centre position array.
        :param size: Node radius.
        :return: PyVista PolyData mesh.
        """
        import pyvista as pv

        if self._lod == "high":
            if kind == "module":
                h = size * 0.9
                return pv.Box(
                    bounds=(
                        center[0] - h, center[0] + h,
                        center[1] - h, center[1] + h,
                        center[2] - h, center[2] + h,
                    )
                )
            elif kind == "function":
                return pv.Cylinder(
                    center=center,
                    direction=(0, 0, 1),
                    radius=size * 0.6,
                    height=size * 1.4,
                    resolution=12,
                )
            else:
                # class, method, symbol → icosphere
                return pv.Icosphere(radius=size, nsub=1, center=center)

        elif self._lod == "low":
            h = size * 0.9
            return pv.Box(
                bounds=(
                    center[0] - h, center[0] + h,
                    center[1] - h, center[1] + h,
                    center[2] - h, center[2] + h,
                )
            )
        else:
            # "points" — minimal geometry
            return pv.Sphere(
                radius=size * 0.5,
                center=center,
                theta_resolution=4,
                phi_resolution=4,
            )

    def _render_nodes(self) -> None:
        """Add all node meshes to the plotter with kind-based colours."""
        for node in self._nodes:
            pos = self._positions.get(node.id)
            if pos is None:
                continue
            size = _KIND_SIZE.get(node.kind, 0.3)
            color = _KIND_COLOR.get(node.kind, "#AAAAAA")
            mesh = self._node_mesh(node.kind, pos, size)
            self._plotter.add_mesh(
                mesh,
                color=color,
                smooth_shading=True,
                name=node.id,
            )

    # ------------------------------------------------------------------
    # Edge rendering
    # ------------------------------------------------------------------

    def _render_edges(self) -> None:
        """Render cross-cutting edges as coloured Bézier arcs or lines."""
        import pyvista as pv

        for edge in self._edges:
            src_pos = self._positions.get(edge.src)
            dst_pos = self._positions.get(edge.dst)
            if src_pos is None or dst_pos is None:
                continue

            color = _REL_COLOR.get(edge.rel, "#AAAAAA")

            if edge.rel == "CONTAINS":
                if not self.show_contains:
                    continue
                line = pv.Line(src_pos, dst_pos)
                self._plotter.add_mesh(
                    line, color=color, line_width=0.5, opacity=0.25
                )

            elif edge.rel in self.rel_filter:
                arc_pts = _arc_points(src_pos, dst_pos)
                spline = pv.Spline(arc_pts, n_points=24)

                if self._lod == "high":
                    mesh = spline.tube(radius=0.04)
                    self._plotter.add_mesh(mesh, color=color, opacity=0.75)
                else:
                    self._plotter.add_mesh(
                        spline, color=color, line_width=1.5, opacity=0.65
                    )

    # ------------------------------------------------------------------
    # Picking
    # ------------------------------------------------------------------

    def _on_pick(self, point: np.ndarray) -> None:
        """
        Handle a pick event: find the nearest node and print its info.

        :param point: World-space pick coordinates from PyVista.
        """
        if not self._positions:
            return

        pt = np.asarray(point, dtype=float)
        best_id = min(
            self._positions,
            key=lambda nid: float(np.linalg.norm(self._positions[nid] - pt)),
        )

        node = next((n for n in self._nodes if n.id == best_id), None)
        if node is None:
            return

        print(f"\n── {node.kind.upper()}: {node.name} ──")
        if node.module_path:
            print(f"   module  : {node.module_path}")
        if node.lineno:
            end = node.end_lineno or "?"
            print(f"   lines   : {node.lineno}–{end}")
        print(f"   id      : {node.id}")
        doc = self._id_to_doc.get(node.id, "(no docstring)")
        if doc != "(no docstring)":
            # Truncate for console readability
            snippet = doc[:300] + ("…" if len(doc) > 300 else "")
            print(f"   docstring:\n{snippet}")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Display the 3-D window.  Blocks until the window is closed.

        :raises RuntimeError: If :meth:`build` has not been called.
        """
        if self._plotter is None:
            raise RuntimeError("Call .build() before .show()")
        self._plotter.show()

    def export_html(self, path: str | Path = "codekg_3d.html") -> None:
        """
        Export the scene to a self-contained interactive HTML file.

        :param path: Output file path.
        :raises RuntimeError: If :meth:`build` has not been called.
        """
        if self._plotter is None:
            raise RuntimeError("Call .build() before .export_html()")
        self._plotter.export_html(str(path))
        print(f"[codekg-viz3d] exported → {path}")

    def export_png(self, path: str | Path = "codekg_3d.png") -> None:
        """
        Save a PNG screenshot of the current camera view.

        :param path: Output file path.
        :raises RuntimeError: If :meth:`build` has not been called.
        """
        if self._plotter is None:
            raise RuntimeError("Call .build() before .export_png()")
        self._plotter.screenshot(str(path))
        print(f"[codekg-viz3d] screenshot → {path}")


# ---------------------------------------------------------------------------
# Convenience launcher (used by codekg_viz3d.py CLI)
# ---------------------------------------------------------------------------


def launch(
    db_path: str | Path = ".codekg/graph.sqlite",
    layout_name: str = "allium",
    show_contains: bool = False,
    rels: Optional[Set[str]] = None,
    export_html: Optional[str] = None,
    export_png: Optional[str] = None,
) -> None:
    """
    Build and show the 3-D visualiser; optionally export without opening a window.

    :param db_path: Path to the SQLite database.
    :param layout_name: ``"allium"`` or ``"cake"``.
    :param show_contains: Render CONTAINS edges.
    :param rels: Edge relation types to render (default: CALLS, IMPORTS, INHERITS).
    :param export_html: If set, export to this HTML path and exit.
    :param export_png: If set, save a PNG to this path (window stays open).
    """
    from code_kg.layout3d import AlliumLayout, LayerCakeLayout

    layout_map = {
        "allium": AlliumLayout(),
        "cake": LayerCakeLayout(),
    }
    layout = layout_map.get(layout_name, AlliumLayout())

    viz = KGViz3D(
        db_path=db_path,
        layout=layout,
        rel_filter=rels or {"CALLS", "IMPORTS", "INHERITS"},
        show_contains=show_contains,
    )
    viz.build()

    if export_html:
        viz.export_html(export_html)
    if export_png:
        viz.export_png(export_png)
    if not export_html:
        viz.show()
