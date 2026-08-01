"""CLI entrypoint for Jupyter2PDF."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Launch the Streamlit application."""
    app = Path(__file__).resolve().parent / "app.py"
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "streamlit", "run", str(app), *sys.argv[1:]])
    )


if __name__ == "__main__":
    main()
