"""
Download AI model weights for FrameFlow AI.

Downloads the DINOv2-Small ONNX model from Hugging Face.
Run with: python scripts/download_models.py
"""

from __future__ import annotations

import sys
import os
import urllib.request
from pathlib import Path

# Ensure project root is on path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from src.utils.constants import AI_MODEL_FILENAME, AI_MODEL_URL, MODELS_DIR


def download_with_progress(url: str, output_path: Path) -> None:
    """Download a file with a progress bar."""
    print(f"  URL: {url}")
    print(f"  Saving to: {output_path}")

    def reporthook(block_num: int, block_size: int, total_size: int) -> None:
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(100, downloaded * 100 // total_size)
            mb_done = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            bar = "█" * (pct // 2) + "░" * (50 - pct // 2)
            print(f"\r  [{bar}] {pct}% ({mb_done:.1f}/{mb_total:.1f} MB)", end="", flush=True)
        else:
            mb_done = downloaded / (1024 * 1024)
            print(f"\r  Downloaded: {mb_done:.1f} MB", end="", flush=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, str(output_path), reporthook=reporthook)
    print()  # Newline after progress bar


def main() -> None:
    print("=" * 60)
    print("  FrameFlow AI — Model Downloader")
    print("=" * 60)

    model_path = MODELS_DIR / AI_MODEL_FILENAME

    if model_path.exists():
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"\n  Model already exists: {model_path} ({size_mb:.1f} MB)")
        response = input("  Re-download? [y/N]: ").strip().lower()
        if response != "y":
            print("  Skipping download.")
            return

    print(f"\n  Downloading DINOv2-Small ONNX model (~85 MB)...")
    try:
        download_with_progress(AI_MODEL_URL, model_path)
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"\n  ✅ Model downloaded successfully ({size_mb:.1f} MB)")
    except Exception as e:
        print(f"\n  ❌ Download failed: {e}")
        print("\n  You can manually download the model from:")
        print(f"  {AI_MODEL_URL}")
        print(f"  Save it to: {model_path}")
        sys.exit(1)

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
