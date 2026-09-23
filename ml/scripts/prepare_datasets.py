#!/usr/bin/env python3
"""
scripts/prepare_datasets.py

1. Ingests raw public datasets (SMCR, Reading Colorimetric) into unified data/processed/ format.
   Preserves original ground-truth labels (e.g. pH remains pH, assay signals remain assay signals).
2. Generates a clearly labelled synthetic target-style dataset in data/synthetic_target_style/
   with realistic lighting casts, shadows, blur, rotation, perspective distortion, and camera noise.
3. Groups data strictly by sample_id into 4 splits: TRAIN, VALIDATION, CALIBRATION, TEST.
4. Generates representative demo images in demo/images/.
"""

import os
import sys
import json
import math
import random
import shutil
import numpy as np
import cv2

DATA_PROCESSED = os.path.abspath("data/processed")
DATA_SYNTHETIC = os.path.abspath("data/synthetic_target_style")
DEMO_IMAGES = os.path.abspath("demo/images")


def setup_directories():
    os.makedirs(DATA_PROCESSED, exist_ok=True)
    os.makedirs(DATA_SYNTHETIC, exist_ok=True)
    os.makedirs(DEMO_IMAGES, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. INGEST REAL DATASETS (SMCR & Reading)
# ---------------------------------------------------------------------------

def process_smcr():
    """Process SMCR pH test-strip images and tags."""
    smcr_dir = os.path.abspath("data/raw/smcr/datasets/training")
    tags_path = os.path.join(smcr_dir, "tags.json")
    if not os.path.exists(tags_path):
        print("[!] SMCR tags.json not found, skipping SMCR processing.")
        return []

    with open(tags_path, "r", encoding="utf-8") as f:
        tags = json.load(f)

    records = []
    # Collect unique sample IDs (each image is a distinct physical strip/test)
    for idx, item in enumerate(tags):
        img_name = item.get("imagePath")
        src_path = os.path.join(smcr_dir, img_name)
        if not os.path.exists(src_path):
            continue

        sample_id = f"smcr_sample_{idx:03d}"
        refs = item.get("references", [])
        ph_val = None
        bbox = None
        if refs:
            r0 = refs[0]
            ph_val = r0.get("result", "")
            pos = r0.get("position", {})
            rect = r0.get("rect", {})
            bbox = {
                "x_frac": pos.get("x", 0.0),
                "y_frac": pos.get("y", 0.0),
                "w_px": rect.get("x", 0),
                "h_px": rect.get("y", 0),
            }

        rec = {
            "image_path": os.path.relpath(src_path, os.getcwd()),
            "source_dataset": "smcr",
            "source_tier": "Tier B",
            "sample_id": sample_id,
            "label": f"pH_{ph_val}" if ph_val else "colorimetric_pad",
            "original_label": ph_val,
            "bbox": bbox,
            "synthetic": False,
            "target_domain": False,
            "analyte": "pH",
            "device": "iPhone 6 Plus"
        }
        records.append(rec)

    print(f"[+] Processed {len(records)} SMCR records.")
    return records


def process_reading():
    """Process University of Reading Colorimetric Dataset."""
    reading_dir = os.path.abspath("data/raw/reading_colorimetric")
    csv_path = os.path.join(reading_dir, "Images_list.csv")
    images_dir = os.path.join(reading_dir, "images", "Dataset")
    if not os.path.exists(csv_path) or not os.path.exists(images_dir):
        # Fallback check
        images_dir = os.path.join(reading_dir, "images")
        if not os.path.exists(images_dir):
            print("[!] Reading Colorimetric images not found, skipping.")
            return []

    import csv
    records = []
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            img_name = row.get("Image Name", "").strip()
            # Search for image in images_dir
            src_path = os.path.join(images_dir, img_name)
            if not os.path.exists(src_path):
                # Search recursively
                found = False
                for r, _, files in os.walk(images_dir):
                    if img_name in files:
                        src_path = os.path.join(r, img_name)
                        found = True
                        break
                if not found:
                    continue

            sample_id = f"reading_sample_{idx:03d}"
            rec = {
                "image_path": os.path.relpath(src_path, os.getcwd()),
                "source_dataset": "reading_colorimetric",
                "source_tier": "Tier B",
                "sample_id": sample_id,
                "label": row.get("Assay", "colorimetric").lower(),
                "original_label": row.get("Image charateristics", ""),
                "bbox": None,
                "synthetic": False,
                "target_domain": False,
                "device": row.get("Camera", "unknown"),
                "notes": row.get("Image charateristics", "")
            }
            records.append(rec)

    print(f"[+] Processed {len(records)} Reading Colorimetric records.")
    return records


# ---------------------------------------------------------------------------
# 2. SYNTHETIC TARGET-STYLE GENERATOR (WITH COMPREHENSIVE VARIATIONS)
# ---------------------------------------------------------------------------

REFERENCE_PATCHES = {
    "white": (243, 243, 242),
    "gray_80": (200, 200, 200),
    "gray_60": (160, 160, 160),
    "gray_40": (122, 122, 121),
    "gray_20": (85, 85, 85),
    "black": (52, 52, 52),
    "red": (173, 35, 35),
    "green": (35, 173, 35),
    "blue": (35, 35, 173),
    "yellow": (219, 219, 35),
    "cyan": (35, 219, 219),
    "magenta": (219, 35, 219),
}

# Standard test pad colors (BGR order) for synthetic target demonstration
PAD_COLOR_MAP = {
    "control_valid": (80, 170, 80),          # Green
    "control_invalid": (210, 210, 210),      # Blank / unreacted
    "opioid_positive": (60, 80, 160),        # Deep purple/red reaction
    "opioid_negative": (205, 215, 225),      # Light beige/unreacted
    "opioid_inconclusive": (120, 135, 185),  # Ambiguous mid-tone
    "stimulant_positive": (190, 140, 80),    # Blue/cobalt reaction
    "stimulant_negative": (205, 215, 225),   # Light beige
    "stimulant_inconclusive": (195, 175, 150),
    "benzo_positive": (190, 110, 160),       # Magenta/violet reaction
    "benzo_negative": (205, 215, 225),       # Light beige
    "benzo_inconclusive": (195, 160, 190),
}


def draw_synthetic_reference_card(canvas, x0, y0, w, h):
    """Render a 4x6 calibration card with 12 known reference patches."""
    cv2.rectangle(canvas, (x0 - 8, y0 - 8), (x0 + w + 8, y0 + h + 8), (250, 250, 250), -1)
    cv2.rectangle(canvas, (x0 - 8, y0 - 8), (x0 + w + 8, y0 + h + 8), (30, 30, 30), 2)
    names = list(REFERENCE_PATCHES.keys())
    rows, cols = 4, 6
    cell_w, cell_h = w / cols, h / rows
    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= len(names):
                break
            rgb = REFERENCE_PATCHES[names[idx]]
            bgr = (rgb[2], rgb[1], rgb[0])
            px0, py0 = int(x0 + c * cell_w), int(y0 + r * cell_h)
            px1, py1 = int(x0 + (c + 1) * cell_w), int(y0 + (r + 1) * cell_h)
            cv2.rectangle(canvas, (px0 + 2, py0 + 2), (px1 - 2, py1 - 2), bgr, -1)
            idx += 1


def draw_synthetic_test_strip(canvas, x0, y0, w, h, pad_colors_bgr):
    """Render a white elongated strip cassette containing 4 distinct reagent pads."""
    # Strip body
    cv2.rectangle(canvas, (x0 - 6, y0 - 6), (x0 + w + 6, y0 + h + 6), (235, 235, 235), -1)
    cv2.rectangle(canvas, (x0 - 6, y0 - 6), (x0 + w + 6, y0 + h + 6), (180, 180, 180), 1)
    n = len(pad_colors_bgr)
    seg_h = h / n
    for i, color in enumerate(pad_colors_bgr):
        py0 = int(y0 + i * seg_h + 8)
        py1 = int(y0 + (i + 1) * seg_h - 8)
        px0 = int(x0 + 10)
        px1 = int(x0 + w - 10)
        cv2.rectangle(canvas, (px0, py0), (px1, py1), color, -1)
        cv2.rectangle(canvas, (px0, py0), (px1, py1), (100, 100, 100), 1)


def generate_single_synthetic_strip(
    state="positive",
    condition="normal",
    canvas_size=(800, 1000),
    rng=None
):
    """
    Builds a synthetic test strip image with reference card and 4 pads.
    States: 'positive', 'negative', 'inconclusive'
    Conditions: 'normal', 'poor_lighting', 'blurred', 'perspective', 'shadow'
    """
    if rng is None:
        rng = np.random.default_rng(42)

    h, w = canvas_size

    # Background texture
    bg_choice = rng.integers(0, 3)
    if bg_choice == 0:
        # Dark lab mat
        canvas = np.full((h, w, 3), int(rng.uniform(45, 70)), dtype=np.uint8)
    elif bg_choice == 1:
        # Wood / warm tabletop
        base_color = np.array([55, 90, 140], dtype=np.float32)
        canvas = np.ones((h, w, 3), dtype=np.float32) * base_color
        grain = rng.normal(0, 8, (h, w, 3))
        canvas = np.clip(canvas + grain, 0, 255).astype(np.uint8)
    else:
        # Neutral grey work surface
        canvas = np.full((h, w, 3), int(rng.uniform(110, 140)), dtype=np.uint8)

    # Reference card geometry
    card_x = int(w * 0.08)
    card_y = int(h * 0.10)
    card_w = int(w * 0.42)
    card_h = int(h * 0.35)
    draw_synthetic_reference_card(canvas, card_x, card_y, card_w, card_h)

    # Reagent pad colors based on target state
    pad_order = ["control", "opioid", "stimulant", "benzo"]
    pad_colors = []
    for analyte in pad_order:
        if analyte == "control":
            col = PAD_COLOR_MAP["control_valid"]
        else:
            key = f"{analyte}_{state}"
            col = PAD_COLOR_MAP.get(key, PAD_COLOR_MAP["opioid_negative"])
        # Add slight natural chemical variance
        var = rng.normal(0, 4, 3)
        col = tuple(int(np.clip(c + v, 0, 255)) for c, v in zip(col, var))
        pad_colors.append(col)

    # Strip geometry
    strip_x = int(w * 0.62)
    strip_y = int(h * 0.12)
    strip_w = int(w * 0.22)
    strip_h = int(h * 0.65)
    draw_synthetic_test_strip(canvas, strip_x, strip_y, strip_w, strip_h, pad_colors)

    # Apply environmental conditions
    out = canvas.copy()

    # Shadows
    if condition == "shadow" or rng.random() < 0.3:
        shadow_mask = np.ones((h, w), dtype=np.float32)
        center_x = int(rng.uniform(0, w))
        for x in range(w):
            factor = max(0.4, min(1.0, 0.5 + 0.5 * (x - center_x) / (w * 0.6)))
            shadow_mask[:, x] = factor
        out = (out.astype(np.float32) * shadow_mask[:, :, None]).clip(0, 255).astype(np.uint8)

    # Poor lighting / underexposure / warm cast
    if condition == "poor_lighting":
        # Heavy underexposure + strong yellow-orange cast
        out = (out.astype(np.float32) * 0.45).astype(np.uint8)
        cast = np.array([0.7, 0.9, 1.25])  # BGR order: strong red/green cast
        out = np.clip(out.astype(np.float32) * cast, 0, 255).astype(np.uint8)
    elif rng.random() < 0.5:
        # Mild ambient lighting variation
        cast_b = rng.uniform(0.92, 1.08)
        cast_g = rng.uniform(0.95, 1.05)
        cast_r = rng.uniform(0.92, 1.08)
        out = np.clip(out.astype(np.float32) * np.array([cast_b, cast_g, cast_r]), 0, 255).astype(np.uint8)

    # Blur
    if condition == "blurred":
        k = int(rng.choice([11, 15, 19]))
        out = cv2.GaussianBlur(out, (k, k), 0)
    elif rng.random() < 0.25:
        k = int(rng.choice([3, 5]))
        out = cv2.GaussianBlur(out, (k, k), 0)

    # Camera sensor noise
    noise_sigma = rng.uniform(2.0, 6.0) if condition != "poor_lighting" else 8.0
    noise = rng.normal(0, noise_sigma, out.shape)
    out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # Perspective distortion / mild rotation
    if condition == "perspective":
        pts1 = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dx1 = rng.uniform(30, 80)
        dy1 = rng.uniform(20, 60)
        dx2 = rng.uniform(-80, -30)
        pts2 = np.float32([[dx1, dy1], [w + dx2, dy1], [w - 30, h - 20], [30, h - 20]])
        M = cv2.getPerspectiveTransform(pts1, pts2)
        out = cv2.warpPerspective(out, M, (w, h), borderValue=(50, 50, 50))
    elif rng.random() < 0.35:
        # Mild rotation (-4 to +4 degrees)
        angle = rng.uniform(-4.0, 4.0)
        M_rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        out = cv2.warpAffine(out, M_rot, (w, h), borderValue=(50, 50, 50))

    # JPEG compression artifact
    quality = int(rng.integers(40, 75)) if condition == "poor_lighting" else int(rng.integers(70, 95))
    _, enc = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, quality])
    out = cv2.imdecode(enc, cv2.IMREAD_COLOR)

    return out


def generate_synthetic_dataset(n_samples=180, seed=42):
    """Generate n_samples synthetic target-style images with sample_id grouping."""
    rng = np.random.default_rng(seed)
    states = ["positive", "negative", "inconclusive"]
    conditions = ["normal", "poor_lighting", "blurred", "perspective", "shadow"]

    records = []
    print(f"[*] Generating {n_samples} synthetic target-style demo images...")

    # Group into physical samples: each physical sample has 2-3 captures
    sample_counter = 0
    img_idx = 0

    while img_idx < n_samples:
        sample_id = f"synth_sample_{sample_counter:04d}"
        sample_state = states[sample_counter % len(states)]
        # 2 to 3 camera captures of this same physical strip
        n_captures = int(rng.integers(2, 4))
        for c_idx in range(n_captures):
            if img_idx >= n_samples:
                break
            cond = conditions[img_idx % len(conditions)] if c_idx > 0 else "normal"
            img = generate_single_synthetic_strip(
                state=sample_state,
                condition=cond,
                canvas_size=(800, 1000),
                rng=rng
            )
            fname = f"synth_strip_{img_idx:04d}_{sample_state}_{cond}.jpg"
            fpath = os.path.join(DATA_SYNTHETIC, fname)
            cv2.imwrite(fpath, img)

            rec = {
                "image_path": os.path.relpath(fpath, os.getcwd()),
                "source_dataset": "synthetic_target_style",
                "source_tier": "Tier D",
                "sample_id": sample_id,
                "label": sample_state,
                "original_label": sample_state,
                "condition": cond,
                "bbox": None,
                "synthetic": True,
                "ground_truth_source": "synthetic",
                "target_validated": False,
                "analyte_panel": ["control", "opioid", "stimulant", "benzo"]
            }
            records.append(rec)
            img_idx += 1
        sample_counter += 1

    print(f"[+] Successfully generated {len(records)} synthetic target-style images across {sample_counter} physical samples.")
    return records


# ---------------------------------------------------------------------------
# 3. GENERATE REPRESENTATIVE DEMO IMAGE SET
# ---------------------------------------------------------------------------

def generate_demo_images():
    """Create curated standalone demo images in demo/images/."""
    demo_specs = [
        ("positive_style.jpg", "positive", "normal"),
        ("negative_style.jpg", "negative", "normal"),
        ("inconclusive_style.jpg", "inconclusive", "normal"),
        ("poor_lighting.jpg", "positive", "poor_lighting"),
        ("blurred.jpg", "positive", "blurred"),
        ("perspective_distorted.jpg", "positive", "perspective"),
    ]

    rng = np.random.default_rng(123)
    manifest = []
    print("[*] Generating curated demo images in demo/images/...")
    for fname, state, cond in demo_specs:
        img = generate_single_synthetic_strip(state=state, condition=cond, rng=rng)
        out_path = os.path.join(DEMO_IMAGES, fname)
        cv2.imwrite(out_path, img)
        manifest.append({
            "filename": fname,
            "path": os.path.relpath(out_path, os.getcwd()),
            "state": state,
            "condition": cond,
            "synthetic_demo": True,
            "target_validated": False,
            "description": f"Synthetic demo test strip: {state} state under {cond} condition."
        })
        print(f"    - Created {fname} [{state}, {cond}]")

    with open(os.path.join(DEMO_IMAGES, "demo_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


# ---------------------------------------------------------------------------
# 4. GROUPED DATA SPLITTING (TRAIN / VAL / CAL / TEST)
# ---------------------------------------------------------------------------

def apply_grouped_split(records, split_ratios=(0.60, 0.15, 0.10, 0.15), seed=42):
    """
    Groups records strictly by sample_id to prevent any physical strip frames
    from leaking across TRAIN, VALIDATION, CALIBRATION, and TEST splits.
    """
    rng = random.Random(seed)
    # Collect sample_ids
    sample_map = {}
    for r in records:
        sid = r["sample_id"]
        sample_map.setdefault(sid, []).append(r)

    unique_samples = list(sample_map.keys())
    rng.shuffle(unique_samples)

    n = len(unique_samples)
    n_train = int(n * split_ratios[0])
    n_val = int(n * split_ratios[1])
    n_cal = int(n * split_ratios[2])

    train_ids = set(unique_samples[:n_train])
    val_ids = set(unique_samples[n_train:n_train + n_val])
    cal_ids = set(unique_samples[n_train + n_val:n_train + n_val + n_cal])
    test_ids = set(unique_samples[n_train + n_val + n_cal:])

    split_counts = {"TRAIN": 0, "VALIDATION": 0, "CALIBRATION": 0, "TEST": 0}

    for sid, recs in sample_map.items():
        if sid in train_ids:
            sp = "TRAIN"
        elif sid in val_ids:
            sp = "VALIDATION"
        elif sid in cal_ids:
            sp = "CALIBRATION"
        else:
            sp = "TEST"
        for r in recs:
            r["split"] = sp
            split_counts[sp] += 1

    print(f"Grouped Split ({len(unique_samples)} unique physical samples -> {len(records)} images):")
    for sp, c in split_counts.items():
        print(f"  - {sp:12s}: {c} images")

    return records


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("=========================================================")
    print("STRIP_ASSAY: DATA PREPARATION & SYNTHETIC DATA GENERATION")
    print("=========================================================")
    setup_directories()

    # 1. Process public real datasets
    smcr_records = process_smcr()
    reading_records = process_reading()

    # 2. Generate synthetic target-style dataset
    synth_records = generate_synthetic_dataset(n_samples=200, seed=42)

    # 3. Create demo images
    generate_demo_images()

    # 4. Grouped split for synthetic target dataset
    synth_split = apply_grouped_split(synth_records, seed=100)

    # 5. Grouped split for real colorimetric dataset (SMCR + Reading)
    real_records = smcr_records + reading_records
    if real_records:
        real_split = apply_grouped_split(real_records, seed=200)
    else:
        real_split = []

    # Save processed manifests
    synth_manifest_path = os.path.join(DATA_PROCESSED, "synthetic_manifest.json")
    with open(synth_manifest_path, "w", encoding="utf-8") as f:
        json.dump(synth_split, f, indent=2)

    real_manifest_path = os.path.join(DATA_PROCESSED, "real_colorimetric_manifest.json")
    with open(real_manifest_path, "w", encoding="utf-8") as f:
        json.dump(real_split, f, indent=2)

    # Unified master dataset index
    unified_records = real_split + synth_split
    master_path = os.path.join(DATA_PROCESSED, "unified_metadata.jsonl")
    with open(master_path, "w", encoding="utf-8") as f:
        for r in unified_records:
            f.write(json.dumps(r) + "\n")

    print(f"\n[+] Processing complete.")
    print(f"    - Synthetic manifest: {synth_manifest_path} ({len(synth_split)} records)")
    print(f"    - Real colorimetric manifest: {real_manifest_path} ({len(real_split)} records)")
    print(f"    - Unified metadata index: {master_path} ({len(unified_records)} total records)")


if __name__ == "__main__":
    main()
