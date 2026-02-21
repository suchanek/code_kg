#!/usr/bin/env python3
"""
codekg_viz.py — CLI launcher for the CodeKG Streamlit visualizer.

Usage:
    codekg-viz [--db PATH] [--port PORT]

Launches ``streamlit run`` against the bundled app.py in the package directory.
Works both from the source tree and when installed from a wheel.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Launch the CodeKG Streamlit visualizer.")
    parser.add_argument(
        "--db",
        default=".codekg/graph.sqlite",
        help="Path to the SQLite database (default: .codekg/graph.sqlite)",
    )
    parser.add_argument(
        "--port",
        default="8500",
        help="Streamlit server port (default: 8500)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser window automatically",
    )
    args = parser.parse_args()

    # app.py is bundled alongside this module in the package directory
    app_path = Path(__file__).parent / "app.py"

    if not app_path.exists():
        print(
            f"ERROR: Could not find app.py at {app_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(args.port),
        "--",
        "--db",
        args.db,
    ]
    if args.no_browser:
        cmd[5:5] = ["--server.headless", "true"]

    print(f"Launching CodeKG Explorer on http://localhost:{args.port}")
    print(f"  app   : {app_path}")
    print(f"  db    : {args.db}")
    print("  Press Ctrl+C to stop.\n")

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
