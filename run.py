"""Quick launcher for FrameFlow AI — runs standalone with crash logging."""
import sys
import os
import traceback

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LOG_FILE = os.path.join(os.path.expanduser("~"), ".frameflow_ai", "crash.log")

if __name__ == "__main__":
    try:
        from src.app import run_app
        run_app()
    except SystemExit:
        pass
    except Exception:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "w") as f:
            traceback.print_exc(file=f)
        traceback.print_exc()
        input("Press Enter to close...")
