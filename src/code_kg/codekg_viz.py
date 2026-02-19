#!/usr/bin/env python3
"""
codekg_viz.py — CLI launcher for the CodeKG Streamlit visualizer.

Usage:
    codekg-viz [--db PATH] [--port PORT]

Launches `streamlit run app.py` from the package root.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Launch the CodeKG Streamlit visualizer."
    )
    parser.add_argument(
        "--db",
        default="codekg.sqlite",
        help="Path to the SQLite database (default: codekg.sqlite)",
    )
    parser.add_argument(
        "--port",
        default="8501",
        help="Streamlit server port (default: 8501)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser window automatically",
    )
    args = parser.parse_args()

    # Locate app.py — first check CWD, then the package root
    app_path = Path("app.py")
    if not app_path.exists():
        # Fall back to the directory containing this file's package root
        pkg_root = Path(__file__).parent.parent.parent
        app_path = pkg_root / "app.py"

    if not app_path.exists():
        print(
            f"ERROR: Could not find app.py. "
            f"Run codekg-viz from the code_kg repository root.",
            file=sys.stderr,
        )
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--server.port", args.port,
        "--",
        "--db", args.db,
    ]
    if args.no_browser:
        cmd[4:4] = ["--server.headless", "true"]

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
