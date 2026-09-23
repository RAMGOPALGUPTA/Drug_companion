"""
Test-strip ROI (region of interest) extraction.

Locates the strip within the frame and returns fixed-position crops for
each reagent pad, plus a background/blank reference region used to check
for illumination gradients across the strip itself.
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import numpy as np
import cv2


@dataclass
class ROIResult:
    strip_found: bool
    pad_rois: Dict[str, np.ndarray]       # analyte name -> cropped BGR patch
    pad_mean_rgb: Dict[str, Tuple[float, float, float]]
    failure_reason: Optional[str] = None


def locate_strip(image_bgr: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Locate the test strip's bounding box using color-based segmentation
    (strips are typically white/light plastic against a darker mat/card).
    Returns (x, y, w, h) or None.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    image_area = image_bgr.shape[0] * image_bgr.shape[1]
    candidates = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < 0.01 * image_area or area > 0.9 * image_area:
            continue
        aspect = max(w, h) / max(1, min(w, h))
        if aspect < 2.0:  # strips are elongated
            continue
        candidates.append((area, (x, y, w, h)))

    if not candidates:
        return None

    candidates.sort(key=lambda t: -t[0])
    return candidates[0][1]


def extract_pad_rois(image_bgr: np.ndarray, strip_bbox: Tuple[int, int, int, int],
                      pad_names: List[str], orientation: str = "vertical",
                      pad_size_frac: float = 0.6) -> ROIResult:
    """
    Given the strip bounding box, slice it into equal segments along its
    long axis (one per pad, in order) and sample the mean color of the
    central region of each segment.

    Args:
        pad_names: ordered list, e.g. ["control", "opioid", "stimulant", "benzo"]
        orientation: "vertical" (pads stacked top-to-bottom) or "horizontal"
        pad_size_frac: fraction of each segment's width/height sampled,
                       centered, to avoid edge artifacts.
    """
    x, y, w, h = strip_bbox
    n = len(pad_names)
    if n == 0:
        return ROIResult(False, {}, {}, failure_reason="no_pad_names_provided")

    rois: Dict[str, np.ndarray] = {}
    means: Dict[str, Tuple[float, float, float]] = {}

    if orientation == "vertical":
        seg_h = h / n
        for i, name in enumerate(pad_names):
            seg_y0 = y + i * seg_h
            seg_y1 = y + (i + 1) * seg_h
            cy = (seg_y0 + seg_y1) / 2
            half_h = seg_h * pad_size_frac / 2
            half_w = w * pad_size_frac / 2
            cx = x + w / 2
            y0, y1 = int(cy - half_h), int(cy + half_h)
            x0, x1 = int(cx - half_w), int(cx + half_w)
            crop = image_bgr[max(0, y0):y1, max(0, x0):x1]
            if crop.size == 0:
                continue
            rois[name] = crop
            mean_bgr = crop.reshape(-1, 3).mean(axis=0)
            means[name] = (float(mean_bgr[2]), float(mean_bgr[1]), float(mean_bgr[0]))
    else:
        seg_w = w / n
        for i, name in enumerate(pad_names):
            seg_x0 = x + i * seg_w
            seg_x1 = x + (i + 1) * seg_w
            cx = (seg_x0 + seg_x1) / 2
            half_w = seg_w * pad_size_frac / 2
            half_h = h * pad_size_frac / 2
            cy = y + h / 2
            x0, x1 = int(cx - half_w), int(cx + half_w)
            y0, y1 = int(cy - half_h), int(cy + half_h)
            crop = image_bgr[max(0, y0):y1, max(0, x0):x1]
            if crop.size == 0:
                continue
            rois[name] = crop
            mean_bgr = crop.reshape(-1, 3).mean(axis=0)
            means[name] = (float(mean_bgr[2]), float(mean_bgr[1]), float(mean_bgr[0]))

    if len(rois) < n:
        return ROIResult(False, rois, means, failure_reason="one_or_more_pads_failed_to_crop")

    return ROIResult(True, rois, means)


def extract_rois(image_bgr: np.ndarray, pad_names: List[str],
                  orientation: str = "vertical") -> ROIResult:
    """End-to-end: locate strip, then slice pads."""
    bbox = locate_strip(image_bgr)
    if bbox is None:
        return ROIResult(False, {}, {}, failure_reason="strip_not_located")
    return extract_pad_rois(image_bgr, bbox, pad_names, orientation)
