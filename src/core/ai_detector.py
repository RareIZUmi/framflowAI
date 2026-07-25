"""
AI-based dead frame detection using DINOv2-Small for FrameFlow AI.

Uses a pre-trained DINOv2 Vision Transformer (exported to ONNX) as a
feature extractor. Compares cosine similarity of frame embeddings to
distinguish:
  - Actual motion (camera shake, facial movements, lighting changes)
  - Truly duplicated / held animation frames

The deep features are more robust than pixel-level comparisons because
they capture semantic and structural information:
  - Compression artifacts → same deep features
  - Film grain / noise → same deep features
  - Actual content change → different deep features

Model: DINOv2-Small (ViT-S/14) — 384-dim embeddings, ~85 MB ONNX.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.utils.constants import (
    AI_FEATURE_DIM,
    AI_MODEL_FILENAME,
    AI_MODEL_INPUT_SIZE,
    AI_MODEL_URL,
    MODELS_DIR,
)
from src.utils.logger import get_logger

logger = get_logger("core.ai_detector")


# ---------------------------------------------------------------------------
# AI Detector
# ---------------------------------------------------------------------------

class AIDetector:
    """
    DINOv2-Small feature extractor for dead frame detection.

    Extracts 384-dim embeddings from frames and compares them via
    cosine similarity. Designed to be used as the `ai_scorer` callable
    injected into DuplicateDetector.

    Usage:
        detector = AIDetector()
        if detector.available:
            similarity = detector.compare_frames(frame_a, frame_b)
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        gpu_enabled: bool = True,
        gpu_device_id: int = 0,
    ) -> None:
        self._model_path = Path(model_path) if model_path else MODELS_DIR / AI_MODEL_FILENAME
        self._gpu_enabled = gpu_enabled
        self._gpu_device_id = gpu_device_id
        self._session: Any | None = None  # onnxruntime.InferenceSession
        self._lock = threading.Lock()
        self._input_name: str = ""
        self._output_name: str = ""

        self._initialize()

    # -- Initialization -----------------------------------------------------

    def _initialize(self) -> None:
        """Load the ONNX model if available."""
        if not self._model_path.exists():
            logger.warning(
                "AI model not found at %s. AI detection disabled. "
                "Run 'python scripts/download_models.py' to download.",
                self._model_path,
            )
            return

        try:
            import onnxruntime as ort

            # Select execution providers
            providers = self._get_providers()
            logger.info("ONNX Runtime providers: %s", providers)

            self._session = ort.InferenceSession(
                str(self._model_path),
                providers=providers,
            )

            self._input_name = self._session.get_inputs()[0].name
            self._output_name = self._session.get_outputs()[0].name

            logger.info(
                "AI model loaded: %s (input=%s, output=%s)",
                self._model_path.name,
                self._input_name,
                self._output_name,
            )
        except ImportError:
            logger.warning("onnxruntime not installed. AI detection disabled.")
        except Exception as exc:
            logger.error("Failed to load AI model: %s", exc)
            self._session = None

    def _get_providers(self) -> list[str]:
        """Determine ONNX Runtime execution providers based on available hardware."""
        import onnxruntime as ort

        available = ort.get_available_providers()
        providers: list[str] = []

        if self._gpu_enabled:
            # Prefer CUDA, then DirectML, then OpenCL
            if "CUDAExecutionProvider" in available:
                providers.append("CUDAExecutionProvider")
            if "DmlExecutionProvider" in available:
                providers.append("DmlExecutionProvider")

        # Always include CPU as fallback
        providers.append("CPUExecutionProvider")
        return providers

    # -- Properties ---------------------------------------------------------

    @property
    def available(self) -> bool:
        """Whether the AI model is loaded and ready."""
        return self._session is not None

    @property
    def model_path(self) -> Path:
        return self._model_path

    # -- Preprocessing ------------------------------------------------------

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """
        Preprocess a BGR frame for DINOv2 inference.

        Steps:
        1. Convert BGR → RGB
        2. Resize to model input size (518×518 for DINOv2)
        3. Normalize with ImageNet mean/std
        4. Transpose to NCHW format
        """
        # BGR to RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Resize to model input size
        resized = cv2.resize(
            rgb,
            AI_MODEL_INPUT_SIZE,
            interpolation=cv2.INTER_AREA if frame.shape[0] > AI_MODEL_INPUT_SIZE[0] else cv2.INTER_LINEAR,
        )

        # Normalize to [0, 1] then apply ImageNet stats
        normalized = resized.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        normalized = (normalized - mean) / std

        # HWC → CHW → NCHW
        tensor = np.transpose(normalized, (2, 0, 1))
        tensor = np.expand_dims(tensor, axis=0)
        return tensor

    # -- Inference ----------------------------------------------------------

    def extract_features(self, frame: np.ndarray) -> np.ndarray | None:
        """
        Extract DINOv2 feature embedding from a single frame.

        Args:
            frame: BGR numpy array.

        Returns:
            1-D numpy array of shape (384,), or None if AI is not available.
        """
        if not self.available:
            return None

        try:
            input_tensor = self._preprocess(frame)
            with self._lock:
                outputs = self._session.run(
                    [self._output_name],
                    {self._input_name: input_tensor},
                )
            # DINOv2 outputs [batch, feature_dim]
            embedding = outputs[0][0]  # Shape: (384,)
            return embedding.astype(np.float32)
        except Exception as exc:
            logger.warning("AI feature extraction failed: %s", exc)
            return None

    def compare_frames(self, frame_a: np.ndarray, frame_b: np.ndarray) -> float:
        """
        Compute cosine similarity between two frames' deep features.

        This is the callable injected into DuplicateDetector as `ai_scorer`.

        Args:
            frame_a: Previous frame (BGR).
            frame_b: Current frame (BGR).

        Returns:
            Cosine similarity in [0, 1] where 1 = identical features.
        """
        feat_a = self.extract_features(frame_a)
        feat_b = self.extract_features(frame_b)

        if feat_a is None or feat_b is None:
            return 0.0

        return self._cosine_similarity(feat_a, feat_b)

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        sim = dot / (norm_a * norm_b)
        # Clamp to [0, 1] (cosine sim can be negative but for our
        # purpose that means "very different" → 0)
        return float(max(0.0, min(1.0, sim)))

    # -- Batch Inference (for perf) -----------------------------------------

    def extract_features_batch(self, frames: list[np.ndarray]) -> list[np.ndarray | None]:
        """
        Extract features from multiple frames.

        Currently runs sequentially but prepared for batched ONNX inference.

        Args:
            frames: List of BGR numpy arrays.

        Returns:
            List of feature vectors (or None for failures).
        """
        return [self.extract_features(f) for f in frames]

    # -- Model Download Helper ----------------------------------------------

    @staticmethod
    def download_model(
        url: str | None = None,
        output_path: str | Path | None = None,
        progress_callback: Any = None,
    ) -> Path:
        """
        Download the ONNX model file.

        Args:
            url: Download URL (defaults to AI_MODEL_URL).
            output_path: Where to save (defaults to MODELS_DIR / AI_MODEL_FILENAME).
            progress_callback: Optional callable(bytes_downloaded, total_bytes).

        Returns:
            Path to the downloaded file.
        """
        import urllib.request

        url = url or AI_MODEL_URL
        output_path = Path(output_path) if output_path else MODELS_DIR / AI_MODEL_FILENAME
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Downloading AI model from %s ...", url)

        def _reporthook(block_num: int, block_size: int, total_size: int) -> None:
            downloaded = block_num * block_size
            if progress_callback:
                progress_callback(downloaded, total_size)

        urllib.request.urlretrieve(url, str(output_path), reporthook=_reporthook)
        logger.info("AI model downloaded to %s", output_path)
        return output_path
