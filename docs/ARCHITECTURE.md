# FrameFlow AI — Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     FrameFlow AI                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────── UI Layer ─────────────────────────┐  │
│  │  MainWindow ──┬── ImportPanel ──── DropZone           │  │
│  │               ├── PreviewWidget ── VideoPlayerWidget   │  │
│  │               ├── TimelineWidget ─ TimelineCanvas      │  │
│  │               ├── BatchPanel ──── Queue Table          │  │
│  │               ├── LogViewer                            │  │
│  │               ├── SettingsDialog                       │  │
│  │               └── ExportDialog                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌──────────────── Core Engine ──────────────────────────┐  │
│  │  VideoLoader ─── FFprobeManager                       │  │
│  │       │                                               │  │
│  │  FrameExtractor ─── FrameCache (LRU)                  │  │
│  │       │                                               │  │
│  │  DuplicateDetector ──┬── SSIM                         │  │
│  │       │              ├── pHash                        │  │
│  │       │              ├── Histogram                    │  │
│  │       │              ├── Optical Flow                 │  │
│  │       │              └── AI Features ─── AIDetector   │  │
│  │       │                                  (DINOv2)     │  │
│  │  SceneDetector                                        │  │
│  │       │                                               │  │
│  │  Exporter ─── FFmpeg subprocess                       │  │
│  │       │       Audio trimmer                           │  │
│  │       └────── ReportGenerator                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌──────────────── Infrastructure ───────────────────────┐  │
│  │  GPUManager (CUDA / DirectML / CPU)                   │  │
│  │  SettingsManager (JSON persistence)                   │  │
│  │  Logger (rotating file + console)                     │  │
│  │  FFmpegManager (auto-detect + subprocess)             │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

```
Video File
    │
    ▼
VideoLoader.load()          ← FFprobe metadata extraction
    │
    ▼
FrameExtractor              ← Multi-threaded producer/consumer
    │                         + LRU cache + thumbnail generation
    ▼
┌─── Frame Pair (prev, current) ───┐
│                                   │
│  ┌─ SceneDetector ────────────┐  │
│  │  Histogram diff > threshold │  │
│  │  → Scene boundary (KEEP)    │  │
│  └─────────────────────────────┘  │
│                                   │
│  ┌─ DuplicateDetector ────────┐  │
│  │  SSIM ──────── 0.30 ──┐    │  │
│  │  pHash ─────── 0.20 ──┤    │  │
│  │  Histogram ─── 0.15 ──┤    │  │
│  │  Optical Flow─ 0.25 ──┼─→ Weighted Score  │
│  │  AI Features── 0.10 ──┘    │  │
│  │                             │  │
│  │  Score > 0.97 → REMOVE      │  │
│  │  Score > 0.90 → UNCERTAIN   │  │
│  │  Score < 0.90 → KEEP        │  │
│  └─────────────────────────────┘  │
└───────────────────────────────────┘
    │
    ▼
FrameAnalysis[]             ← Per-frame results
    │
    ▼
┌─── Timeline + Preview ───┐
│  Color-coded visualization │
│  Manual override (K/R)     │
│  Undo/Redo stack           │
└────────────────────────────┘
    │
    ▼
Exporter
    ├── Write kept frames → temp PNGs
    ├── FFmpeg encode → video
    ├── Extract audio → WAV
    ├── Surgical audio trim (per removed frame)
    ├── Mux video + audio → final output
    └── Generate JSON/CSV reports
```

## Key Design Decisions

1. **Weighted Multi-Algorithm Scoring** — No single algorithm is reliable enough alone.
   SSIM handles compression artifacts, pHash is fast and noise-tolerant, Optical Flow
   detects actual motion, and AI features provide semantic understanding.

2. **Scene-Aware Detection** — Scene boundaries are detected first and always kept.
   This prevents the detector from marking the first frame of a cut as a "dead frame"
   of the last frame of the previous scene.

3. **Compare Against Last Unique Frame** — When a dead frame is found, subsequent frames
   are compared against the last *unique* frame, not the duplicate. This correctly
   detects runs of 3+ held frames.

4. **Surgical Audio Trimming** — Instead of re-timing or stretching audio, we cut out
   the exact audio segments corresponding to removed frames. This preserves lip sync
   and musical timing throughout.

5. **Non-blocking UI** — Frame analysis runs via QTimer batching (10 frames per tick),
   keeping the UI responsive. The timeline updates progressively during analysis.

6. **DINOv2 via ONNX Runtime** — Using ONNX instead of raw PyTorch eliminates the
   need to bundle a 2 GB PyTorch installation. ONNX Runtime is ~50 MB and supports
   CUDA, DirectML, and CPU inference.
