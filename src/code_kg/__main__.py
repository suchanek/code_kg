"""Dispatcher for ``python -m code_kg <subcommand> [args…]``.

Allows CodeKG to be invoked without activating a virtual environment or
relying on ``poetry run``, as long as the package is installed in the
active Python environment (e.g. via ``pip install code-kg``).

Subcommands
-----------
build-sqlite    Build the SQLite knowledge graph
build-lancedb   Build the LanceDB semantic index
query           Run a hybrid query
pack            Generate a snippet pack
viz             Launch the Streamlit visualiser
mcp             Start the MCP server
"""

import sys

_COMMANDS: dict[str, str] = {
    "build-sqlite": "code_kg.build_codekg_sqlite",
    "build-lancedb": "code_kg.build_codekg_lancedb",
    "query": "code_kg.codekg_query",
    "pack": "code_kg.codekg_snippet_packer",
    "viz": "code_kg.codekg_viz",
    "mcp": "code_kg.mcp_server",
}

_HELP = """\
usage: python -m code_kg <subcommand> [options]

subcommands:
  build-sqlite    Build the SQLite knowledge graph
  build-lancedb   Build the LanceDB semantic index
  query           Run a hybrid query
  pack            Generate a snippet pack
  viz             Launch the Streamlit visualiser
  mcp             Start the MCP server

Run  python -m code_kg <subcommand> --help  for per-command options.
"""


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(_HELP, end="")
        sys.exit(0)

    subcommand = sys.argv[1]
    if subcommand not in _COMMANDS:
        print(f"error: unknown subcommand '{subcommand}'\n", file=sys.stderr)
        print(_HELP, end="", file=sys.stderr)
        sys.exit(1)

    # Rewrite argv so the target module's argparse sees a clean sys.argv:
    #   ["code_kg", "build-sqlite", "--repo", "."]
    #   → ["code_kg build-sqlite", "--repo", "."]
    sys.argv = [f"python -m code_kg {subcommand}", *sys.argv[2:]]

    import importlib

    mod = importlib.import_module(_COMMANDS[subcommand])
    mod.main()


if __name__ == "__main__":
    main()
