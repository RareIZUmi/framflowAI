# FrameFlow AI

**Intelligent Dead Frame Remover for Video Editors**

FrameFlow AI automatically detects and removes duplicated animation frames (dead frames, held frames, freeze frames) from videos using a multi-algorithm AI-powered detection pipeline.

---

## Features

- **Multi-Algorithm Detection**: SSIM, Perceptual Hash, Histogram Comparison, Optical Flow, and DINOv2 AI Feature Extraction
- **Weighted Confidence Scoring**: Combines all algorithms into a single dead frame probability
- **Professional UI**: Dark theme inspired by DaVinci Resolve with timeline, side-by-side preview, and batch processing
- **GPU Acceleration**: CUDA, DirectML, and OpenCL support with CPU fallback
- **Manual Override**: Keep/remove individual frames with undo/redo
- **Flexible Export**: H.264, H.265, ProRes, DNxHD, FFV1, PNG/JPEG/EXR sequences
- **Audio Sync**: Surgical audio trimming at exact removed-frame timestamps
- **Batch Processing**: Queue multiple videos with progress tracking
- **Scene Detection**: Prevents false positives at scene boundaries
- **Reports**: JSON and CSV per-frame analysis reports

## Quick Start

### Prerequisites

- Python 3.11+
- FFmpeg (must be on PATH or installed to a standard location)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-repo/frameflow-ai.git
cd frameflow-ai

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Download AI model (~85 MB)
python scripts/download_models.py
```

### Run

```bash
python -m src.main
```

### Run Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

## Building a Standalone Executable

```bash
# Install build dependencies
pip install -r requirements-dev.txt

# Build with PyInstaller
python scripts/build.py

# Output: dist/FrameFlowAI/FrameFlowAI.exe
# Portable: dist/FrameFlowAI-portable.zip
```

### Creating a Windows Installer

1. Install [Inno Setup 6+](https://jrsoftware.org/isinfo.php)
2. Run `python scripts/build.py` first
3. Open `scripts/create_installer.iss` in Inno Setup Compiler
4. Click Build → installer output in `installer/`

## Architecture

```
src/
├── core/                  # Processing engine
│   ├── video_loader.py    # FFprobe metadata + OpenCV capture
│   ├── frame_extractor.py # Multi-threaded frame reading
│   ├── duplicate_detector.py  # 5-algorithm weighted scoring
│   ├── ai_detector.py     # DINOv2-Small ONNX inference
│   ├── scene_detector.py  # Shot boundary detection
│   ├── exporter.py        # Video/image export via FFmpeg
│   └── frame_cache.py     # LRU memory cache
├── ui/                    # PySide6 interface
│   ├── main_window.py     # Central window + orchestration
│   ├── timeline_widget.py # Color-coded frame timeline
│   ├── preview_widget.py  # Side-by-side video preview
│   ├── batch_panel.py     # Multi-video queue
│   ├── settings_dialog.py # 5-tab settings
│   ├── export_dialog.py   # Export configuration
│   └── theme.py           # Professional dark theme
├── gpu/                   # GPU detection and management
├── utils/                 # Settings, logging, FFmpeg, reports
├── app.py                 # QApplication lifecycle + splash
└── main.py                # Entry point
```

## Detection Pipeline

Each frame is compared against the previous unique frame using five algorithms:

| Algorithm | Weight | What It Measures |
|-----------|--------|-----------------|
| SSIM | 30% | Structural similarity (robust to compression) |
| pHash | 20% | Perceptual hash distance (fast, noise-tolerant) |
| Histogram | 15% | Color distribution correlation |
| Optical Flow | 25% | Motion magnitude (Farneback dense flow) |
| AI Features | 10% | DINOv2 deep feature cosine similarity |

The weighted average produces a **dead frame probability** (0–100%).  
Frames above the **similarity threshold** (default 97%) are marked for removal.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open video |
| `Ctrl+R` | Analyze video |
| `Ctrl+E` | Export |
| `Space` | Play / Pause |
| `←` / `→` | Frame backward / forward |
| `K` | Keep selected frame |
| `R` | Remove selected frame |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Ctrl+=` / `Ctrl+-` | Zoom timeline |
| `Ctrl+,` | Settings |

## License

MIT License — see [LICENSE](LICENSE) for details.
