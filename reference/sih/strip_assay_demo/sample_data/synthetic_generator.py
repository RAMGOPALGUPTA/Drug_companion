"""
Synthetic frame generator: produces a fake reference card + test strip
image for pipeline smoke-testing without needing a real photo. Also
supports batch generation with augmentation (blur/noise/compression) for
ML training data, per the project's "Data" key decision.
"""
from typing import Tuple
import numpy as np
import cv2

from core.config import DEFAULT_CONFIG


def _draw_reference_card(canvas: np.ndarray, x0: int, y0: int, w: int, h: int) -> None:
    cfg = DEFAULT_CONFIG.calibration
    names = list(cfg.reference_patches.keys())
    rows, cols = cfg.reference_grid_shape
    cell_w, cell_h = w / cols, h / rows

    cv2.rectangle(canvas, (x0 - 10, y0 - 10), (x0 + w + 10, y0 + h + 10), (255, 255, 255), -1)

    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= len(names):
                break
            rgb = cfg.reference_patches[names[idx]]
            bgr = (rgb[2], rgb[1], rgb[0])
            px0, py0 = int(x0 + c * cell_w), int(y0 + r * cell_h)
            px1, py1 = int(x0 + (c + 1) * cell_w), int(y0 + (r + 1) * cell_h)
            cv2.rectangle(canvas, (px0, py0), (px1, py1), bgr, -1)
            idx += 1


def _draw_strip(canvas: np.ndarray, x0: int, y0: int, w: int, h: int,
                 pad_colors_bgr) -> None:
    cv2.rectangle(canvas, (x0 - 8, y0 - 8), (x0 + w + 8, y0 + h + 8), (235, 235, 235), -1)
    n = len(pad_colors_bgr)
    seg_h = h / n
    for i, color in enumerate(pad_colors_bgr):
        y1 = int(y0 + i * seg_h)
        y2 = int(y0 + (i + 1) * seg_h)
        cv2.rectangle(canvas, (x0, y1), (x0 + w, y2), color, -1)
        cv2.rectangle(canvas, (x0, y1), (x0 + w, y2), (60, 60, 60), 2)


def generate_synthetic_frame(seed: int = 42, canvas_size: Tuple[int, int] = (900, 1200),
                              positive_analytes=("opioid",)) -> np.ndarray:
    """
    Build a synthetic BGR image containing a reference color card and a
    test strip with 4 pads (control, opioid, stimulant, benzo), colored
    near their configured Delta-E reference endpoints so the pipeline can
    be smoke-tested end-to-end without a real photograph.
    """
    rng = np.random.default_rng(seed)
    h, w = canvas_size
    canvas = np.full((h, w, 3), 90, dtype=np.uint8)  # dark neutral background for contrast

    # Reference card, top-left
    _draw_reference_card(canvas, x0=60, y0=60, w=500, h=300)

    # Build strip pad colors from Delta-E reference Lab values (approx, via
    # simple inverse using a nearby known sRGB anchor for visualization only)
    de_cfg = DEFAULT_CONFIG.delta_e
    approx_rgb = {
        "opioid_positive": (150, 90, 70), "opioid_negative": (225, 210, 205),
        "stimulant_positive": (120, 150, 200), "stimulant_negative": (225, 210, 205),
        "benzo_positive": (170, 130, 210), "benzo_negative": (225, 210, 205),
        "control_positive": (90, 160, 90),
    }
    pad_order = ["control", "opioid", "stimulant", "benzo"]
    pad_colors_bgr = []
    for analyte in pad_order:
        if analyte == "control":
            rgb = approx_rgb["control_positive"]
        else:
            key = f"{analyte}_positive" if analyte in positive_analytes else f"{analyte}_negative"
            rgb = approx_rgb[key]
        pad_colors_bgr.append((rgb[2], rgb[1], rgb[0]))

    _draw_strip(canvas, x0=650, y0=80, w=180, h=560, pad_colors_bgr=pad_colors_bgr)

    # Mild synthetic lighting cast + noise to simulate field conditions
    cast = np.array([1.05, 1.0, 0.95])  # slight warm cast, BGR order applied loosely
    canvas = np.clip(canvas.astype(np.float64) * cast, 0, 255).astype(np.uint8)
    noise = rng.normal(0, 3, canvas.shape)
    canvas = np.clip(canvas.astype(np.float64) + noise, 0, 255).astype(np.uint8)

    return canvas


def augment_frame(frame: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Apply random blur / noise / JPEG-compression augmentation."""
    out = frame.copy()

    if rng.random() < 0.5:
        k = int(rng.choice([3, 5, 7]))
        out = cv2.GaussianBlur(out, (k, k), 0)

    if rng.random() < 0.5:
        noise = rng.normal(0, rng.uniform(2, 12), out.shape)
        out = np.clip(out.astype(np.float64) + noise, 0, 255).astype(np.uint8)

    if rng.random() < 0.5:
        quality = int(rng.integers(35, 90))
        ok, enc = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if ok:
            out = cv2.imdecode(enc, cv2.IMREAD_COLOR)

    if rng.random() < 0.3:
        gamma = rng.uniform(0.7, 1.4)
        inv = 1.0 / gamma
        table = ((np.arange(256) / 255.0) ** inv * 255).astype(np.uint8)
        out = cv2.LUT(out, table)

    return out


def generate_dataset(output_dir: str, n_samples: int = 100, seed: int = 0) -> None:
    """Batch-generate augmented synthetic frames for ML training/eval."""
    import os
    os.makedirs(output_dir, exist_ok=True)
    rng = np.random.default_rng(seed)
    analytes_all = ["opioid", "stimulant", "benzo"]

    manifest = []
    for i in range(n_samples):
        n_pos = int(rng.integers(0, len(analytes_all) + 1))
        positives = tuple(rng.choice(analytes_all, size=n_pos, replace=False))
        frame = generate_synthetic_frame(seed=int(rng.integers(0, 1_000_000)),
                                          positive_analytes=positives)
        frame = augment_frame(frame, rng)
        fname = f"synthetic_{i:04d}.jpg"
        cv2.imwrite(os.path.join(output_dir, fname), frame)
        manifest.append({"file": fname, "positive_analytes": list(positives)})

    import json
    with open(os.path.join(output_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
