"""
FrameFlow AI – Intelligent Dead Frame Remover for Video Editors.

Entry point for the application.
Usage:
    python -m src.main
"""

from __future__ import annotations

import sys
import os

# Ensure the project root is on the path when running as a script
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def main() -> None:
    """Application entry point."""
    from src.app import run_app
    run_app()


if __name__ == "__main__":
    main()
