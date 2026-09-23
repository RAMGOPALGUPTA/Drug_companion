"""
CIEDE2000 Delta-E rule-based classification engine.

This is the primary, explainable decision path: convert a calibrated
sRGB pad color to CIELAB, compute CIEDE2000 distance to each candidate
reference endpoint (e.g. "positive" / "negative" color chips), and pick
the nearest — subject to confident-match / confident-nonmatch bands.
Colors landing in the ambiguous middle band are marked "inconclusive"
and deferred to the ML confidence layer.
"""
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import math
import numpy as np

from .config import DeltaEConfig


# ---------------------------------------------------------------------------
# Color space conversion: sRGB -> CIELAB (D65 reference white)
# ---------------------------------------------------------------------------

def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def rgb_to_xyz(rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
    r, g, b = srgb_to_linear(np.array(rgb, dtype=np.float64))
    # sRGB D65 matrix
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    return x * 100, y * 100, z * 100


def xyz_to_lab(xyz: Tuple[float, float, float]) -> Tuple[float, float, float]:
    # D65 reference white
    xn, yn, zn = 95.0489, 100.0, 108.8840
    x, y, z = xyz[0] / xn, xyz[1] / yn, xyz[2] / zn

    def f(t):
        delta = 6 / 29
        return t ** (1 / 3) if t > delta ** 3 else t / (3 * delta ** 2) + 4 / 29

    fx, fy, fz = f(x), f(y), f(z)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)
    return L, a, b


def rgb_to_lab(rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return xyz_to_lab(rgb_to_xyz(rgb))


# ---------------------------------------------------------------------------
# CIEDE2000
# ---------------------------------------------------------------------------

def delta_e_ciede2000(lab1: Tuple[float, float, float],
                       lab2: Tuple[float, float, float]) -> float:
    """
    Standard CIEDE2000 color difference formula.
    Reference: Sharma, Wu & Dalal (2005).
    """
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    kL = kC = kH = 1.0

    C1 = math.sqrt(a1 ** 2 + b1 ** 2)
    C2 = math.sqrt(a2 ** 2 + b2 ** 2)
    C_bar = (C1 + C2) / 2.0

    G = 0.5 * (1 - math.sqrt((C_bar ** 7) / (C_bar ** 7 + 25 ** 7)))
    a1p = (1 + G) * a1
    a2p = (1 + G) * a2

    C1p = math.sqrt(a1p ** 2 + b1 ** 2)
    C2p = math.sqrt(a2p ** 2 + b2 ** 2)

    def hue_angle(ap, b):
        if ap == 0 and b == 0:
            return 0.0
        h = math.degrees(math.atan2(b, ap))
        return h + 360 if h < 0 else h

    h1p = hue_angle(a1p, b1)
    h2p = hue_angle(a2p, b2)

    dLp = L2 - L1
    dCp = C2p - C1p

    if C1p * C2p == 0:
        dhp = 0.0
    else:
        diff = h2p - h1p
        if abs(diff) <= 180:
            dhp = diff
        elif diff > 180:
            dhp = diff - 360
        else:
            dhp = diff + 360

    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2)

    L_bar_p = (L1 + L2) / 2.0
    C_bar_p = (C1p + C2p) / 2.0

    if C1p * C2p == 0:
        h_bar_p = h1p + h2p
    else:
        diff = abs(h1p - h2p)
        summ = h1p + h2p
        if diff <= 180:
            h_bar_p = summ / 2
        elif summ < 360:
            h_bar_p = (summ + 360) / 2
        else:
            h_bar_p = (summ - 360) / 2

    T = (1 - 0.17 * math.cos(math.radians(h_bar_p - 30))
         + 0.24 * math.cos(math.radians(2 * h_bar_p))
         + 0.32 * math.cos(math.radians(3 * h_bar_p + 6))
         - 0.20 * math.cos(math.radians(4 * h_bar_p - 63)))

    d_theta = 30 * math.exp(-(((h_bar_p - 275) / 25) ** 2))
    RC = 2 * math.sqrt((C_bar_p ** 7) / (C_bar_p ** 7 + 25 ** 7))
    SL = 1 + (0.015 * (L_bar_p - 50) ** 2) / math.sqrt(20 + (L_bar_p - 50) ** 2)
    SC = 1 + 0.045 * C_bar_p
    SH = 1 + 0.015 * C_bar_p * T
    RT = -math.sin(math.radians(2 * d_theta)) * RC

    dE = math.sqrt(
        (dLp / (kL * SL)) ** 2
        + (dCp / (kC * SC)) ** 2
        + (dHp / (kH * SH)) ** 2
        + RT * (dCp / (kC * SC)) * (dHp / (kH * SH))
    )
    return dE


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

@dataclass
class DeltaEVerdict:
    analyte: str
    call: str                      # "positive" | "negative" | "inconclusive"
    distance_to_positive: float
    distance_to_negative: float
    observed_lab: Tuple[float, float, float]
    explanation: str

    def to_dict(self) -> dict:
        return {
            "analyte": self.analyte,
            "call": self.call,
            "distance_to_positive": round(self.distance_to_positive, 3),
            "distance_to_negative": round(self.distance_to_negative, 3),
            "observed_lab": tuple(round(v, 3) for v in self.observed_lab),
            "explanation": self.explanation,
        }


def classify_pad(analyte: str, observed_rgb: Tuple[float, float, float],
                  cfg: DeltaEConfig) -> DeltaEVerdict:
    """
    Classify a single reagent pad's calibrated RGB reading against the
    positive/negative reference endpoints for its analyte.
    """
    pos_key = f"{analyte}_positive"
    neg_key = f"{analyte}_negative"
    if pos_key not in cfg.analyte_reference_lab or neg_key not in cfg.analyte_reference_lab:
        return DeltaEVerdict(
            analyte=analyte, call="inconclusive",
            distance_to_positive=float("nan"), distance_to_negative=float("nan"),
            observed_lab=(float("nan"),) * 3,
            explanation=f"no reference endpoints configured for analyte '{analyte}'",
        )

    observed_lab = rgb_to_lab(observed_rgb)
    lab_pos = cfg.analyte_reference_lab[pos_key]
    lab_neg = cfg.analyte_reference_lab[neg_key]

    d_pos = delta_e_ciede2000(observed_lab, lab_pos)
    d_neg = delta_e_ciede2000(observed_lab, lab_neg)

    nearest_dist = min(d_pos, d_neg)
    nearest_call = "positive" if d_pos < d_neg else "negative"

    if nearest_dist <= cfg.confident_match_threshold:
        call = nearest_call
        explanation = (f"dE2000 to {nearest_call} reference = {nearest_dist:.2f} "
                        f"(<= confident threshold {cfg.confident_match_threshold})")
    elif d_pos > cfg.confident_nonmatch_threshold and d_neg > cfg.confident_nonmatch_threshold:
        call = "inconclusive"
        explanation = (f"dE2000 to both references exceeds nonmatch threshold "
                        f"({cfg.confident_nonmatch_threshold}); pad color unrecognized")
    else:
        call = "inconclusive"
        explanation = (f"dE2000 nearest = {nearest_dist:.2f} falls in ambiguous band "
                        f"({cfg.confident_match_threshold}-{cfg.confident_nonmatch_threshold}); "
                        f"deferring to ML confidence layer")

    return DeltaEVerdict(
        analyte=analyte, call=call,
        distance_to_positive=d_pos, distance_to_negative=d_neg,
        observed_lab=observed_lab, explanation=explanation,
    )


def classify_all_pads(pad_rgb: Dict[str, Tuple[float, float, float]],
                       cfg: DeltaEConfig) -> Dict[str, DeltaEVerdict]:
    return {analyte: classify_pad(analyte, rgb, cfg) for analyte, rgb in pad_rgb.items()
            if analyte != "control"}
