# User Guide

## Getting Started

### 1. Open a Video

- Click **📂 Open** in the toolbar, or
- Press **Ctrl+O**, or
- **Drag and drop** a video file onto the application window

Supported formats: MP4, MKV, MOV, AVI, WebM

Once loaded, you'll see video metadata (resolution, FPS, codec, duration, frame count) in the Import panel.

### 2. Analyze the Video

- Click **🔍 Analyze** in the toolbar, or
- Press **Ctrl+R**, or
- Go to **Process → Analyze Video**

The analysis runs through every frame and compares it to the previous unique frame using five algorithms:
- **SSIM** — Structural similarity
- **pHash** — Perceptual hashing
- **Histogram** — Color distribution
- **Optical Flow** — Motion detection
- **AI Features** — DINOv2 deep learning (optional)

Progress is shown in the status bar and timeline updates in real-time.

### 3. Review the Timeline

The timeline shows every frame color-coded:
- 🟢 **Green** — Keep (unique frame)
- 🔴 **Red** — Remove (dead/duplicate frame)
- 🟡 **Yellow** — Uncertain (borderline)
- 🔵 **Blue** — Scene boundary

**Click** any frame to preview it in the side-by-side view.
**Right-click** to manually change the decision (Keep / Remove / Uncertain).

### 4. Manual Override

If the automatic detection made an incorrect decision:
- Select the frame on the timeline
- Press **K** to keep it, or **R** to remove it
- Use **Ctrl+Z** / **Ctrl+Shift+Z** to undo/redo

### 5. Export

- Click **💾 Export** or press **Ctrl+E**
- Choose between **Video**, **Image Sequence**, or **Reports Only**
- Configure codec, quality, FPS, and audio handling
- Click **Export**

---

## Settings

Access via **⚙ Settings** or **Ctrl+,**

### Detection Tab
- **Similarity Threshold** — Higher = fewer frames removed (default: 0.97)
- **Uncertain Threshold** — Below this = definitely keep (default: 0.90)
- **Min Consecutive Frames** — Require N duplicates in a row before removal
- **Scene Threshold** — Sensitivity for scene change detection
- **Algorithm Weights** — Adjust the influence of each detection method

### AI Tab
- Enable/disable AI detection mode
- AI confidence threshold

### Export Tab
- Default codec, FPS, and audio settings

### Performance Tab
- GPU device selection
- Frame cache size (default: 2 GB)
- Processing batch size

### Appearance Tab
- Theme (Dark)
- Preview quality
- Frame number display

---

## Batch Processing

1. Open the **Batch Queue** panel
2. Click **➕ Add Files** to queue multiple videos
3. Click **🚀 Process All** to analyze them sequentially
4. Each video shows individual progress
5. Use **Pause** / **Cancel** to control the queue

---

## Tips

- **Zoom the timeline**: Ctrl+Scroll or use View → Zoom In/Out
- **Navigate frames**: Left/Right arrow keys for frame-by-frame stepping
- **Play preview**: Press Space to play/pause
- **Scene boundaries are always kept**: The first frame of each scene is never removed
- **Uncertain frames default to Keep**: Conservative approach — you can change this in settings
