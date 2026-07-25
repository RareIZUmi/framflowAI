"""
GPU detection and management for FrameFlow AI.

Auto-detects available GPU backends and provides a unified interface
for CUDA, DirectML, and OpenCL acceleration. Falls back to CPU when
no GPU is available.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from src.utils.logger import get_logger

logger = get_logger("gpu.gpu_manager")


# ---------------------------------------------------------------------------
# GPU Device Info
# ---------------------------------------------------------------------------

@dataclass
class GPUDevice:
    """Information about a detected GPU device."""

    index: int
    name: str
    backend: str  # "cuda", "directml", "opencl", "cpu"
    vram_total_mb: int = 0
    vram_free_mb: int = 0
    compute_capability: str = ""

    @property
    def display_name(self) -> str:
        vram = f" ({self.vram_total_mb} MB)" if self.vram_total_mb > 0 else ""
        return f"{self.name}{vram} [{self.backend.upper()}]"

    @property
    def is_gpu(self) -> bool:
        return self.backend != "cpu"


# ---------------------------------------------------------------------------
# GPU Manager
# ---------------------------------------------------------------------------

class GPUManager:
    """
    Manages GPU device detection and selection.

    Probes the system for available GPU backends in priority order:
    1. CUDA (NVIDIA)
    2. DirectML (Windows, any GPU)
    3. OpenCL (cross-platform)
    4. CPU (fallback)

    Usage:
        gpu = GPUManager()
        print(gpu.devices)
        print(gpu.selected_device)
        ort_providers = gpu.get_onnx_providers()
    """

    def __init__(self, preferred_device_index: int = 0) -> None:
        self._devices: list[GPUDevice] = []
        self._selected_index: int = 0
        self._detect_devices()
        self.select_device(preferred_device_index)

    # -- Detection ----------------------------------------------------------

    def _detect_devices(self) -> None:
        """Probe the system for all available GPU devices."""
        self._devices.clear()

        # Try CUDA (NVIDIA)
        self._detect_cuda()

        # Try DirectML (Windows)
        self._detect_directml()

        # Always add CPU fallback
        self._devices.append(GPUDevice(
            index=len(self._devices),
            name="CPU",
            backend="cpu",
        ))

        logger.info(
            "Detected %d compute device(s): %s",
            len(self._devices),
            ", ".join(d.display_name for d in self._devices),
        )

    def _detect_cuda(self) -> None:
        """Detect NVIDIA CUDA GPUs."""
        try:
            import subprocess
            # Use nvidia-smi to detect GPUs
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if result.returncode == 0:
                for i, line in enumerate(result.stdout.strip().split("\n")):
                    if line.strip():
                        parts = [p.strip() for p in line.split(",")]
                        name = parts[0] if len(parts) > 0 else f"NVIDIA GPU {i}"
                        vram_total = int(float(parts[1])) if len(parts) > 1 else 0
                        vram_free = int(float(parts[2])) if len(parts) > 2 else 0
                        self._devices.append(GPUDevice(
                            index=len(self._devices),
                            name=name,
                            backend="cuda",
                            vram_total_mb=vram_total,
                            vram_free_mb=vram_free,
                        ))
        except Exception:
            pass  # No CUDA available

        # Also check via ONNX Runtime
        if not any(d.backend == "cuda" for d in self._devices):
            try:
                import onnxruntime as ort
                if "CUDAExecutionProvider" in ort.get_available_providers():
                    self._devices.append(GPUDevice(
                        index=len(self._devices),
                        name="NVIDIA GPU (via ONNX)",
                        backend="cuda",
                    ))
            except ImportError:
                pass

    def _detect_directml(self) -> None:
        """Detect DirectML devices (Windows)."""
        if os.name != "nt":
            return

        try:
            import onnxruntime as ort
            if "DmlExecutionProvider" in ort.get_available_providers():
                # DirectML supports any GPU on Windows (NVIDIA, AMD, Intel)
                self._devices.append(GPUDevice(
                    index=len(self._devices),
                    name="DirectML GPU",
                    backend="directml",
                ))
        except ImportError:
            pass

    # -- Selection ----------------------------------------------------------

    def select_device(self, index: int) -> None:
        """Select a compute device by index."""
        if 0 <= index < len(self._devices):
            self._selected_index = index
            logger.info("Selected device: %s", self._devices[index].display_name)
        else:
            # Fall back to last device (CPU)
            self._selected_index = len(self._devices) - 1
            logger.warning("Invalid device index %d; falling back to CPU.", index)

    @property
    def selected_device(self) -> GPUDevice:
        """Currently selected compute device."""
        return self._devices[self._selected_index]

    @property
    def devices(self) -> list[GPUDevice]:
        """All detected compute devices."""
        return list(self._devices)

    @property
    def has_gpu(self) -> bool:
        """Whether at least one GPU is available."""
        return any(d.is_gpu for d in self._devices)

    # -- ONNX Runtime Integration -------------------------------------------

    def get_onnx_providers(self) -> list[str | tuple[str, dict[str, Any]]]:
        """
        Get ONNX Runtime execution providers for the selected device.

        Returns a list suitable for ort.InferenceSession(providers=...).
        """
        device = self.selected_device
        providers: list[str | tuple[str, dict[str, Any]]] = []

        if device.backend == "cuda":
            providers.append(("CUDAExecutionProvider", {
                "device_id": 0,
                "arena_extend_strategy": "kSameAsRequested",
            }))
        elif device.backend == "directml":
            providers.append("DmlExecutionProvider")

        # Always add CPU fallback
        providers.append("CPUExecutionProvider")
        return providers

    def get_opencv_backend(self) -> int:
        """Get the OpenCV DNN backend for the selected device."""
        device = self.selected_device
        if device.backend == "cuda":
            return cv2.dnn.DNN_BACKEND_CUDA if hasattr(cv2.dnn, "DNN_BACKEND_CUDA") else cv2.dnn.DNN_BACKEND_DEFAULT
        return cv2.dnn.DNN_BACKEND_DEFAULT

    def get_opencv_target(self) -> int:
        """Get the OpenCV DNN target for the selected device."""
        device = self.selected_device
        if device.backend == "cuda":
            return cv2.dnn.DNN_TARGET_CUDA if hasattr(cv2.dnn, "DNN_TARGET_CUDA") else cv2.dnn.DNN_TARGET_CPU
        return cv2.dnn.DNN_TARGET_CPU

    # -- Memory Monitoring --------------------------------------------------

    def refresh_vram(self) -> None:
        """Refresh VRAM usage for CUDA devices."""
        for device in self._devices:
            if device.backend == "cuda":
                try:
                    import subprocess
                    result = subprocess.run(
                        ["nvidia-smi", "--query-gpu=memory.free",
                         "--format=csv,noheader,nounits",
                         f"--id={device.index}"],
                        capture_output=True, text=True, timeout=5,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                    if result.returncode == 0:
                        device.vram_free_mb = int(float(result.stdout.strip()))
                except Exception:
                    pass


# Lazy import for cv2 in type hints
try:
    import cv2
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: GPUManager | None = None


def get_gpu_manager() -> GPUManager:
    """Return the global GPUManager singleton."""
    global _instance  # noqa: PLW0603
    if _instance is None:
        _instance = GPUManager()
    return _instance
