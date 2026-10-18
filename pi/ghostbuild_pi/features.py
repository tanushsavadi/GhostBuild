"""Frame -> contract CameraObs feature maths (numpy only).

Features describe the frame; the core decides what they mean. No thresholds live here
except the per-pixel motion threshold (a measurement parameter, not a judgement).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Optional, Sequence, Tuple

import numpy as np

TARGET_W, TARGET_H = 160, 120
DEFAULT_MOTION_PIXEL_THRESHOLD = 25.0  # abs luma diff (0..255) that counts as a changed pixel

Roi = Tuple[float, float, float, float]  # fractions of the frame: x0, y0, x1, y1


def parse_roi(text: str) -> Roi:
    """'x0,y0,x1,y1' as fractions 0..1 of the frame (x right, y down)."""
    try:
        vals = [float(p) for p in text.split(",")]
    except ValueError as e:
        raise ValueError("ROI must be 4 comma-separated numbers: x0,y0,x1,y1") from e
    if len(vals) != 4:
        raise ValueError("ROI must have exactly 4 numbers: x0,y0,x1,y1")
    x0, y0, x1, y1 = vals
    if not all(0.0 <= v <= 1.0 for v in vals):
        raise ValueError("ROI values are fractions of the frame and must be within 0..1")
    if not (x0 < x1 and y0 < y1):
        raise ValueError("ROI needs x0 < x1 and y0 < y1")
    return (x0, y0, x1, y1)


def to_gray(frame: np.ndarray) -> np.ndarray:
    """HxW, HxWx1, HxWx3 or HxWx4 uint8/float -> HxW float32 luma (0..255)."""
    a = np.asarray(frame)
    if a.ndim == 3 and a.shape[2] == 1:
        a = a[:, :, 0]
    if a.ndim == 2:
        return a.astype(np.float32)
    if a.ndim == 3 and a.shape[2] in (3, 4):
        rgb = a[:, :, :3].astype(np.float32)
        # Channel order (RGB vs BGR) only shifts luma slightly; consistent within a run.
        return rgb[:, :, 0] * 0.299 + rgb[:, :, 1] * 0.587 + rgb[:, :, 2] * 0.114
    raise ValueError("unsupported frame shape %r" % (a.shape,))


def downscale(gray: np.ndarray, target: Tuple[int, int] = (TARGET_W, TARGET_H)) -> np.ndarray:
    """Block-mean downscale toward target (w, h). Never upsamples."""
    h, w = gray.shape
    tw, th = target
    fy, fx = max(1, h // th), max(1, w // tw)
    if fy == 1 and fx == 1:
        return gray
    ny, nx = h // fy, w // fx
    return gray[: ny * fy, : nx * fx].reshape(ny, fy, nx, fx).mean(axis=(1, 3))


def laplacian_variance(gray: np.ndarray) -> float:
    """Variance of the 4-neighbour Laplacian over the interior pixels."""
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    c = gray[1:-1, 1:-1]
    lap = gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4.0 * c
    return float(lap.var())


def _roi_slice(shape: Tuple[int, int], roi: Optional[Roi]) -> Tuple[slice, slice]:
    h, w = shape
    if roi is None:
        return slice(0, h), slice(0, w)
    x0, y0, x1, y1 = roi
    px0, px1 = int(math.floor(x0 * w)), int(math.ceil(x1 * w))
    py0, py1 = int(math.floor(y0 * h)), int(math.ceil(y1 * h))
    px1, py1 = max(px1, px0 + 1), max(py1, py0 + 1)
    return slice(py0, min(py1, h)), slice(px0, min(px1, w))


def motion_fraction(prev: Optional[np.ndarray], cur: np.ndarray, roi: Optional[Roi] = None,
                    threshold: float = DEFAULT_MOTION_PIXEL_THRESHOLD) -> float:
    """Fraction (0..1) of ROI pixels whose abs diff vs the previous frame exceeds threshold."""
    if prev is None or prev.shape != cur.shape:
        return 0.0
    ys, xs = _roi_slice(cur.shape, roi)
    d = np.abs(cur[ys, xs] - prev[ys, xs])
    if d.size == 0:
        return 0.0
    return float((d > threshold).mean())


@dataclass(frozen=True)
class FrameFeatures:
    mean_luma: float
    luma_std: float
    detail: float
    motion: float

    def with_motion(self, motion: float) -> "FrameFeatures":
        return replace(self, motion=motion)


def _clean(v: float, lo: float, hi: float = float("inf")) -> float:
    if v is None or not math.isfinite(v):
        return lo
    return float(min(max(v, lo), hi))


class FeatureExtractor:
    """Stateful: keeps the previous downscaled frame for motion. Call process() per NEW frame only."""

    def __init__(self, roi: Optional[Roi] = None, motion_threshold: float = DEFAULT_MOTION_PIXEL_THRESHOLD,
                 target: Tuple[int, int] = (TARGET_W, TARGET_H)):
        self.roi = roi
        self.motion_threshold = motion_threshold
        self.target = target
        self._prev: Optional[np.ndarray] = None

    def reset(self) -> None:
        self._prev = None

    def process(self, frame: np.ndarray) -> FrameFeatures:
        small = downscale(to_gray(frame), self.target)
        motion = motion_fraction(self._prev, small, self.roi, self.motion_threshold)
        self._prev = small
        return FrameFeatures(
            mean_luma=round(_clean(float(small.mean()), 0.0, 255.0), 2),
            luma_std=round(_clean(float(small.std()), 0.0), 2),
            detail=round(_clean(laplacian_variance(small), 0.0), 2),
            motion=round(_clean(motion, 0.0, 1.0), 4),
        )


def summarize(values: Sequence[float]) -> dict:
    """min / median / max helper used by the spike."""
    if not values:
        return {"n": 0, "min": None, "median": None, "max": None}
    arr = np.asarray(values, dtype=np.float64)
    return {"n": int(arr.size), "min": float(arr.min()), "median": float(np.median(arr)), "max": float(arr.max())}
