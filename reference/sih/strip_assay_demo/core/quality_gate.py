"""
Quality gate: rejects frames that are too blurry, over/under exposed, or
otherwise unsuitable for colorimetric analysis *before* any calibration
or classification work happens. This protects evidentiary validity by
ensuring a documented, reproducible reason for any "inconclusive" result
that stems from image quality rather than the analyte itself.
"""
from dataclasses import dataclass
from typing import List
import numpy as np
import cv2

from .config import QualityGateConfig


@dataclass
class QualityReport:
    passed: bool
    blur_variance: float
    mean_luminance: float
    clipped_fraction: float
    failure_reasons: List[str]

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "blur_variance": round(self.blur_variance, 3),
            "mean_luminance": round(self.mean_luminance, 3),
            "clipped_fraction": round(self.clipped_fraction, 5),
            "failure_reasons": self.failure_reasons,
        }


def _blur_variance(gray: np.ndarray) -> float:
    """Variance of the Laplacian. Low variance => blurry image."""
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(lap.var())


def _exposure_stats(gray: np.ndarray, cfg: QualityGateConfig) -> tuple:
    mean_lum = float(gray.mean())
    clipped = np.logical_or(gray <= 2, gray >= 253)
    clipped_fraction = float(clipped.sum()) / gray.size
    return mean_lum, clipped_fraction


def run_quality_gate(image_bgr: np.ndarray, cfg: QualityGateConfig) -> QualityReport:
    """
    Evaluate an input frame against blur/exposure criteria.

    Args:
        image_bgr: HxWx3 uint8 image as loaded by cv2 (BGR order).
        cfg: QualityGateConfig thresholds.

    Returns:
        QualityReport with pass/fail and diagnostic values.
    """
    if image_bgr is None or image_bgr.size == 0:
        return QualityReport(False, 0.0, 0.0, 1.0, ["empty_image"])

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur_var = _blur_variance(gray)
    mean_lum, clipped_frac = _exposure_stats(gray, cfg)

    reasons: List[str] = []
    if blur_var < cfg.blur_variance_threshold:
        reasons.append(f"blur_variance {blur_var:.1f} < threshold {cfg.blur_variance_threshold}")
    if mean_lum < cfg.min_mean_luminance:
        reasons.append(f"underexposed: mean_luminance {mean_lum:.1f} < {cfg.min_mean_luminance}")
    if mean_lum > cfg.max_mean_luminance:
        reasons.append(f"overexposed: mean_luminance {mean_lum:.1f} > {cfg.max_mean_luminance}")
    if clipped_frac > cfg.max_clipped_fraction:
        reasons.append(f"clipped_fraction {clipped_frac:.4f} > {cfg.max_clipped_fraction}")

    return QualityReport(
        passed=len(reasons) == 0,
        blur_variance=blur_var,
        mean_luminance=mean_lum,
        clipped_fraction=clipped_frac,
        failure_reasons=reasons,
    )
