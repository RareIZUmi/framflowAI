# Deployment Guide

## Overview

FrameFlow AI can be deployed as:
1. **Source distribution** — Python + pip install
2. **Standalone executable** — PyInstaller bundle (no Python required)
3. **Windows installer** — Inno Setup .exe installer
4. **Portable ZIP** — Extract and run

---

## 1. Source Distribution

### Requirements
- Python 3.11+
- FFmpeg on PATH

### Steps
```bash
git clone <repo-url>
cd frameflow-ai
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python scripts/download_models.py
python -m src.main
```

---

## 2. Standalone Executable

### Build

```bash
pip install -r requirements-dev.txt
python scripts/build.py
```

### Output

```
dist/
├── FrameFlowAI/
│   ├── FrameFlowAI.exe         # Main executable
│   ├── _internal/              # Bundled Python + dependencies
│   └── src/resources/models/   # AI model (if downloaded before build)
└── FrameFlowAI-portable.zip    # Portable distribution
```

### FFmpeg

The standalone executable still requires FFmpeg to be available.
Users must either:
- Install FFmpeg and add it to PATH
- Place `ffmpeg.exe` and `ffprobe.exe` in the same directory as `FrameFlowAI.exe`

---

## 3. Windows Installer

### Prerequisites
- [Inno Setup 6+](https://jrsoftware.org/isinfo.php)
- Built dist/FrameFlowAI/ (run `python scripts/build.py` first)

### Build Installer

1. Open `scripts/create_installer.iss` in Inno Setup Compiler
2. Click **Build → Compile**
3. Output: `installer/FrameFlowAI-Setup-1.0.0.exe`

### What the Installer Does
- Installs to `%LOCALAPPDATA%\Programs\FrameFlow AI`
- Creates Start Menu shortcuts
- Optional Desktop shortcut
- Registers video file associations (Open With)
- Includes uninstaller

---

## 4. Portable ZIP

The build script automatically creates `dist/FrameFlowAI-portable.zip`.
Users extract and run `FrameFlowAI.exe` directly — no installation needed.

---

## AI Model

The DINOv2-Small ONNX model (~85 MB) is **not bundled** in the repository.

### For Developers
```bash
python scripts/download_models.py
```
This saves the model to `src/resources/models/dinov2_vits14.onnx`.

### For End Users
The application prompts to download the model on first run if it's missing.
The model is saved to `~/.frameflow_ai/models/`.

### For Builds
If you run `download_models.py` before `build.py`, the model is automatically
bundled into the executable distribution.

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Windows 10 64-bit | Windows 11 |
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| GPU | None (CPU fallback) | NVIDIA GTX 1060+ |
| Disk | 500 MB (app) | 2+ GB (cache) |
| FFmpeg | 4.0+ | 6.0+ |

---

## Troubleshooting

### FFmpeg not found
- Download from https://ffmpeg.org/download.html
- Add the `bin` folder to your system PATH
- Or place `ffmpeg.exe` next to the application

### GPU not detected
- Install the latest GPU drivers
- For CUDA: Install NVIDIA CUDA Toolkit
- For DirectML: Included in Windows 10+
- The app falls back to CPU automatically

### AI model download fails
- Check internet connection
- Download manually from the URL shown in the error
- Place the `.onnx` file in `src/resources/models/`
