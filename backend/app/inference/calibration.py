"""
Reference-card calibration.

Detects a printed reference color card in the frame, samples each known
patch, and fits a 3x3 linear color-correction matrix (least squares) that
maps observed sRGB -> certified sRGB. This corrects for ambient lighting
color casts before any Delta-E comparison is made, which is essential for
field conditions where lighting is uncontrolled.
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import numpy as np
import cv2

from .config import CalibrationConfig


@dataclass
class CalibrationResult:
    matrix: np.ndarray            # 3x3 correction matrix
    residual_mae: float           # mean absolute error of fit, sRGB units
    patch_count: int
    passed: bool
    failure_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "matrix": self.matrix.tolist() if self.matrix is not None else None,
            "residual_mae": round(self.residual_mae, 4),
            "patch_count": self.patch_count,
            "passed": self.passed,
            "failure_reason": self.failure_reason,
        }

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        """Apply the fitted correction matrix to an (N,3) or (3,) sRGB array."""
        single = rgb.ndim == 1
        arr = rgb.reshape(-1, 3).astype(np.float64)
        corrected = arr @ self.matrix.T
        corrected = np.clip(corrected, 0, 255)
        return corrected[0] if single else corrected


def detect_reference_card(image_bgr: np.ndarray) -> Optional[np.ndarray]:
    """
    Locate the reference card via largest quadrilateral contour with a
    strong aspect-ratio + area prior. Returns a perspective-warped,
    axis-aligned crop of the card, or None if not found.

    This is a classical-CV fallback; kits that ship a fiducial/ArUco
    marker on the card should replace this with marker-based detection
    for higher reliability.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    image_area = image_bgr.shape[0] * image_bgr.shape[1]
    best_quad = None
    best_area = 0

    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            area = cv2.contourArea(approx)
            if area > 0.05 * image_area and area > best_area:
                best_area = area
                best_quad = approx

    if best_quad is None:
        return None

    pts = best_quad.reshape(4, 2).astype(np.float32)
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = int(max(width_a, width_b))
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = int(max(height_a, height_b))

    if max_width < 20 or max_height < 20:
        return None

    dst = np.array([
        [0, 0], [max_width - 1, 0],
        [max_width - 1, max_height - 1], [0, max_height - 1],
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image_bgr, M, (max_width, max_height))
    return warped


def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left
    rect[2] = pts[np.argmax(s)]   # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect


def sample_patch_grid(card_bgr: np.ndarray, grid_shape: Tuple[int, int],
                       patch_names: List[str], margin_frac: float = 0.15,
                       sample_frac: float = 0.5) -> Dict[str, Tuple[float, float, float]]:
    """
    Sample the mean sRGB of each cell in a uniform grid over the warped
    card, mapping cell index -> patch_names in row-major order.
    """
    h, w = card_bgr.shape[:2]
    rows, cols = grid_shape
    cell_h, cell_w = h / rows, w / cols
    results = {}

    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= len(patch_names):
                break
            cy = (r + 0.5) * cell_h
            cx = (c + 0.5) * cell_w
            half_h = cell_h * sample_frac / 2
            half_w = cell_w * sample_frac / 2
            y0, y1 = int(cy - half_h), int(cy + half_h)
            x0, x1 = int(cx - half_w), int(cx + half_w)
            y0, x0 = max(0, y0), max(0, x0)
            y1, x1 = min(h, y1), min(w, x1)
            region = card_bgr[y0:y1, x0:x1]
            if region.size == 0:
                idx += 1
                continue
            mean_bgr = region.reshape(-1, 3).mean(axis=0)
            mean_rgb = (float(mean_bgr[2]), float(mean_bgr[1]), float(mean_bgr[0]))
            results[patch_names[idx]] = mean_rgb
            idx += 1
    return results


def fit_calibration_matrix(observed: Dict[str, Tuple[float, float, float]],
                            reference: Dict[str, Tuple[int, int, int]],
                            cfg: CalibrationConfig) -> CalibrationResult:
    """
    Fit a 3x3 matrix M (least squares, no intercept) such that
    observed @ M.T ≈ reference, using patches present in both dicts.
    """
    common = [k for k in reference if k in observed]
    if len(common) < 6:
        return CalibrationResult(
            matrix=np.eye(3), residual_mae=float("inf"), patch_count=len(common),
            passed=False, failure_reason=f"only {len(common)} matched patches (need >=6)"
        )

    obs = np.array([observed[k] for k in common], dtype=np.float64)
    ref = np.array([reference[k] for k in common], dtype=np.float64)

    # Solve obs @ M.T = ref  =>  M.T = lstsq(obs, ref)
    M_T, _, _, _ = np.linalg.lstsq(obs, ref, rcond=None)
    M = M_T.T

    predicted = obs @ M.T
    residual_mae = float(np.mean(np.abs(predicted - ref)))

    passed = residual_mae <= cfg.max_fit_residual
    reason = None if passed else f"residual_mae {residual_mae:.2f} exceeds max {cfg.max_fit_residual}"

    return CalibrationResult(
        matrix=M, residual_mae=residual_mae, patch_count=len(common),
        passed=passed, failure_reason=reason,
    )


def calibrate(image_bgr: np.ndarray, cfg: CalibrationConfig) -> CalibrationResult:
    """End-to-end: detect card, sample patches, fit matrix."""
    card = detect_reference_card(image_bgr)
    if card is None:
        return CalibrationResult(
            matrix=np.eye(3), residual_mae=float("inf"), patch_count=0,
            passed=False, failure_reason="reference_card_not_detected",
        )

    patch_names = list(cfg.reference_patches.keys())
    observed = sample_patch_grid(card, cfg.reference_grid_shape, patch_names)
    return fit_calibration_matrix(observed, cfg.reference_patches, cfg)
