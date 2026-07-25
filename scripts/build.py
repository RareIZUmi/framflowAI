"""
PyInstaller build script for FrameFlow AI.

Creates a single-folder distribution with all dependencies bundled.
Run with: python scripts/build.py

Output: dist/FrameFlowAI/
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_FILE = PROJECT_ROOT / "FrameFlowAI.spec"
SRC_DIR = PROJECT_ROOT / "src"
RESOURCES_DIR = SRC_DIR / "resources"


def clean() -> None:
    """Remove previous build artifacts."""
    for d in (DIST_DIR, BUILD_DIR):
        if d.exists():
            shutil.rmtree(d)
            print(f"  Cleaned: {d}")
    if SPEC_FILE.exists():
        SPEC_FILE.unlink()


def build() -> None:
    """Run PyInstaller to create the distribution."""
    print("=" * 60)
    print("  FrameFlow AI — Build Script")
    print("=" * 60)

    # Step 1: Clean
    print("\n[1/4] Cleaning previous builds...")
    clean()

    # Step 2: Prepare data files
    print("\n[2/4] Preparing resources...")
    datas = []

    # Icons
    icons_dir = RESOURCES_DIR / "icons"
    if icons_dir.exists():
        datas.append((str(icons_dir), "src/resources/icons"))

    # Fonts
    fonts_dir = RESOURCES_DIR / "fonts"
    if fonts_dir.exists():
        datas.append((str(fonts_dir), "src/resources/fonts"))

    # Models (if downloaded)
    models_dir = RESOURCES_DIR / "models"
    if models_dir.exists() and any(models_dir.iterdir()):
        datas.append((str(models_dir), "src/resources/models"))

    # Step 3: Build with PyInstaller
    print("\n[3/4] Running PyInstaller...")

    hidden_imports = [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "cv2",
        "numpy",
        "PIL",
        "skimage",
        "imagehash",
        "onnxruntime",
    ]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "FrameFlowAI",
        "--windowed",
        "--noconfirm",
        "--clean",
        # Icon (if available)
        # "--icon", str(RESOURCES_DIR / "icons" / "app.ico"),
    ]

    for src_path, dest in datas:
        cmd.extend(["--add-data", f"{src_path}{os.pathsep}{dest}"])

    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    # Exclude heavy unused packages
    excludes = ["tkinter", "matplotlib", "scipy", "pandas", "IPython", "jupyter"]
    for exc in excludes:
        cmd.extend(["--exclude-module", exc])

    cmd.append(str(SRC_DIR / "main.py"))

    print(f"  Command: {' '.join(cmd[:10])}...")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        print("\n❌ Build FAILED!")
        sys.exit(1)

    # Step 4: Post-build
    print("\n[4/4] Post-build cleanup...")
    dist_app = DIST_DIR / "FrameFlowAI"
    if dist_app.exists():
        print(f"  ✅ Build successful: {dist_app}")
        print(f"  Size: {_dir_size_mb(dist_app):.1f} MB")

        # Create portable ZIP
        print("  Creating portable ZIP...")
        zip_path = DIST_DIR / "FrameFlowAI-portable"
        shutil.make_archive(str(zip_path), "zip", str(DIST_DIR), "FrameFlowAI")
        print(f"  ✅ Portable ZIP: {zip_path}.zip")
    else:
        print("  ⚠️ dist/FrameFlowAI not found after build.")

    print("\n" + "=" * 60)
    print("  Build complete!")
    print("=" * 60)


def _dir_size_mb(path: Path) -> float:
    """Calculate total directory size in MB."""
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total / (1024 * 1024)


if __name__ == "__main__":
    build()
