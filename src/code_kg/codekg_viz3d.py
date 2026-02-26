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
        "--width",  type=int, default=1400, help="Window width in pixels",
    )
    parser.add_argument(
        "--height", type=int, default=900,  help="Window height in pixels",
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
        db_path=str(db),
        layout_name=args.layout,
        width=args.width,
        height=args.height,
    )


if __name__ == "__main__":
    main()
