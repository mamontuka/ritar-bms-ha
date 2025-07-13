# cli_api.py — adapter for calling cli.py as a function

import shlex
from cli import main as cli_main

def run_debug_cli(args_str: str):
    """Launches the debug CLI with arguments passed as a single string"""
    args = shlex.split(args_str)
    if not args:
        print("❌ No command provided to debug CLI")
        return
    try:
        cli_main(args)
    except SystemExit:
        pass  # Suppress sys.exit() to avoid exiting the shell
