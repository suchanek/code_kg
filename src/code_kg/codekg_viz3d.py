#!/usr/bin/env python3
"""
codekg_viz3d.py — CLI launcher for the CodeKG 3-D PyVista visualiser.

Usage::

    codekg-viz3d [--db PATH] [--layout allium|cake]
                 [--rels CALLS IMPORTS INHERITS]
                 [--show-contains]
                 [--export-html PATH]
                 [--export-png PATH]

Examples::

    # Open interactive window with Allium layout (default)
    codekg-viz3d --db .codekg/graph.sqlite

    # Layer-cake layout showing only inheritance edges
    codekg-viz3d --layout cake --rels INHERITS

    # Export to HTML without opening a window
    codekg-viz3d --export-html my_graph.html

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    """
    Parse CLI arguments and launch the 3-D knowledge-graph visualiser.

    Delegates to :func:`~code_kg.viz3d.launch` after resolving the layout
    strategy and edge filter from the command-line arguments.
    """
    parser = argparse.ArgumentParser(
        prog="codekg-viz3d",
        description="CodeKG 3D — interactive PyVista knowledge-graph explorer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--db",
        default=".codekg/graph.sqlite",
        metavar="PATH",
        help="Path to the SQLite database (default: .codekg/graph.sqlite)",
    )
    parser.add_argument(
        "--layout",
        choices=["allium", "cake"],
        default="allium",
        help=(
            "3-D layout strategy (default: allium). "
            "'allium' renders each module as a Giant Allium plant; "
            "'cake' stratifies nodes by kind across Z layers."
        ),
    )
    parser.add_argument(
        "--rels",
        nargs="+",
        choices=["CALLS", "IMPORTS", "INHERITS"],
        default=["CALLS", "IMPORTS", "INHERITS"],
        metavar="REL",
        help=(
            "Edge relation types to render as arcs "
            "(default: CALLS IMPORTS INHERITS)"
        ),
    )
    parser.add_argument(
        "--show-contains",
        action="store_true",
        help="Render CONTAINS edges as thin grey lines",
    )
    parser.add_argument(
        "--export-html",
        metavar="PATH",
        help="Export the scene to an interactive HTML file and exit",
    )
    parser.add_argument(
        "--export-png",
        metavar="PATH",
        help="Save a PNG screenshot of the current view",
    )

    args = parser.parse_args()

    db = Path(args.db)
    if not db.exists():
        parser.error(
            f"Database not found: {db}\n"
            "Run 'codekg-build-sqlite' first to index your repository."
        )

    from code_kg.viz3d import launch

    launch(
        db_path=db,
        layout_name=args.layout,
        show_contains=args.show_contains,
        rels=set(args.rels),
        export_html=args.export_html,
        export_png=args.export_png,
    )


if __name__ == "__main__":
    main()
