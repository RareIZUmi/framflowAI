# FrameFlow AI – Resources

This directory contains bundled application resources.

## Subdirectories

- `icons/` — SVG/PNG icons for the UI (toolbar, menus, status)
- `fonts/` — Bundled fonts (optional, falls back to system fonts)
- `models/` — AI model weights (ONNX format, downloaded via `scripts/download_models.py`)

## Notes

- Model files (`.onnx`) are **not** tracked in git (see `.gitignore`)
- Run `python scripts/download_models.py` to download the DINOv2-Small model
- Icons can be replaced with custom SVGs for rebranding
