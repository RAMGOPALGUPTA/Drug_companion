#!/usr/bin/env python3
"""
scripts/train_synthetic_demo.py

Trains MobileNetV3-Small secondary confidence classifier on reagent pad crops
from the synthetic target-style dataset.
Classes: ["negative", "positive", "invalid"]

Adheres to:
- Dynamic model input resolution specification
- Saves models/model_metadata.json
- Strictly uses TRAIN and VALIDATION splits (TEST split remains untouched)
- Saves checkpoints to models/checkpoints/ and models/synthetic_demo/
- Clearly labels output as SYNTHETIC DEMO / BOOTSTRAP MODEL (NOT target-validated)
"""

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import json
import time
import numpy as np
import cv2

# Set random seeds for reproducibility
np.random.seed(42)

import tensorflow as tf
tf.random.set_seed(42)

from core.roi_extraction import extract_rois

MODELS_DIR = os.path.abspath("models")
SYNTH_MODEL_DIR = os.path.join(MODELS_DIR, "synthetic_demo")
BOOTSTRAP_MODEL_DIR = os.path.join(MODELS_DIR, "bootstrap")
CHECKPOINTS_DIR = os.path.join(MODELS_DIR, "checkpoints")

CLASS_LABELS = ("negative", "positive", "invalid")
LABEL_TO_IDX = {l: i for i, l in enumerate(CLASS_LABELS)}
INPUT_SHAPE = (224, 224, 3)  # Dynamic input specification


def extract_pad_training_data(manifest_path, target_splits=("TRAIN", "VALIDATION")):
    """Extract individual reagent pad crops and assign labels from manifest."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    split_data = {sp: {"images": [], "labels": []} for sp in target_splits}
    pad_names = ["control", "opioid", "stimulant", "benzo"]

    print(f"[*] Extracting pad crops from {len(records)} images for splits {target_splits}...")
    for rec in records:
        sp = rec.get("split")
        if sp not in target_splits:
            continue

        img_path = rec.get("image_path")
        if not os.path.exists(img_path):
            continue

        bgr = cv2.imread(img_path)
        if bgr is None:
            continue

        state = rec.get("label", "inconclusive")
        cond = rec.get("condition", "normal")

        # Extract ROIs using core pipeline
        roi_res = extract_rois(bgr, pad_names)
        if not roi_res.strip_found or not roi_res.pad_rois:
            # Fallback crop if strip detection fails due to extreme perspective/lighting
            h, w = bgr.shape[:2]
            strip_crop = bgr[int(h*0.15):int(h*0.8), int(w*0.6):int(w*0.88)]
            if strip_crop.size == 0:
                continue
            seg_h = strip_crop.shape[0] / len(pad_names)
            pad_rois = {}
            for i, name in enumerate(pad_names):
                y0, y1 = int(i*seg_h), int((i+1)*seg_h)
                pad_rois[name] = strip_crop[y0:y1, :]
        else:
            pad_rois = roi_res.pad_rois

        for name, crop in pad_rois.items():
            if crop is None or crop.size == 0:
                continue

            # Assign ground truth class label
            if cond in ("blurred", "poor_lighting") and np.random.rand() < 0.25:
                cls_name = "invalid"
            elif name == "control":
                cls_name = "positive"
            else:
                if state == "positive":
                    cls_name = "positive"
                elif state == "negative":
                    cls_name = "negative"
                else:
                    cls_name = "invalid"

            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (INPUT_SHAPE[1], INPUT_SHAPE[0]), interpolation=cv2.INTER_AREA)

            split_data[sp]["images"].append(resized)
            split_data[sp]["labels"].append(LABEL_TO_IDX[cls_name])

    for sp in target_splits:
        print(f"  Split {sp}: {len(split_data[sp]['images'])} pad crops extracted.")
    return split_data


def build_mobilenetv3_model(input_shape=INPUT_SHAPE, num_classes=3):
    """Construct lightweight MobileNetV3-Small transfer learning architecture."""
    base_model = tf.keras.applications.MobileNetV3Small(
        input_shape=input_shape,
        include_top=False,
        weights="imagenet",
        pooling="avg"
    )
    base_model.trainable = True
    # Fine-tune only top blocks to preserve low-level color features
    for layer in base_model.layers[:-25]:
        layer.trainable = False

    inputs = tf.keras.Input(shape=input_shape)
    # Preprocessing: standard scaling [0, 1]
    x = tf.keras.layers.Rescaling(1.0 / 255.0)(inputs)
    # Data augmentation for training robustness
    x = tf.keras.layers.RandomFlip("horizontal_and_vertical")(x)
    x = tf.keras.layers.RandomRotation(0.05)(x)
    x = tf.keras.layers.RandomContrast(0.1)(x)

    features = base_model(x, training=True)
    features = tf.keras.layers.Dropout(0.2)(features)
    outputs = tf.keras.layers.Dense(num_classes, activation="softmax", name="classification_head")(features)

    model = tf.keras.Model(inputs, outputs, name="MobileNetV3_Small_Pad_Classifier")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"]
    )
    return model


def main():
    print("=========================================================")
    print("STRIP_ASSAY: MODEL TRAINING (SYNTHETIC TARGET-STYLE DEMO)")
    print("=========================================================")
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(SYNTH_MODEL_DIR, exist_ok=True)
    os.makedirs(BOOTSTRAP_MODEL_DIR, exist_ok=True)
    os.makedirs(CHECKPOINTS_DIR, exist_ok=True)

    manifest_path = os.path.abspath("data/processed/synthetic_manifest.json")
    if not os.path.exists(manifest_path):
        print(f"[!] Manifest not found at {manifest_path}. Run scripts/prepare_datasets.py first.")
        sys.exit(1)

    # 1. Extract pad crops strictly from TRAIN and VALIDATION splits
    split_data = extract_pad_training_data(manifest_path, ("TRAIN", "VALIDATION"))
    x_train = np.array(split_data["TRAIN"]["images"], dtype=np.uint8)
    y_train = np.array(split_data["TRAIN"]["labels"], dtype=np.int32)
    x_val = np.array(split_data["VALIDATION"]["images"], dtype=np.uint8)
    y_val = np.array(split_data["VALIDATION"]["labels"], dtype=np.int32)

    if len(x_train) == 0:
        print("[!] No training pad crops found.")
        sys.exit(1)

    print(f"\n[*] Training set: {x_train.shape}, Validation set: {x_val.shape}")

    # 2. Build MobileNetV3-Small architecture
    model = build_mobilenetv3_model(INPUT_SHAPE, len(CLASS_LABELS))
    model.summary()

    # 3. Train model with EarlyStopping
    best_checkpoint = os.path.join(CHECKPOINTS_DIR, "best_mobilenetv3.keras")
    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_accuracy", patience=4, restore_best_weights=True),
        tf.keras.callbacks.ModelCheckpoint(best_checkpoint, monitor="val_accuracy", save_best_only=True)
    ]

    print("\n[*] Starting training (8 epochs)...")
    history = model.fit(
        x_train, y_train,
        validation_data=(x_val, y_val),
        epochs=8,
        batch_size=16,
        callbacks=callbacks,
        verbose=1
    )

    # 4. Save model artifacts
    synth_keras_path = os.path.join(SYNTH_MODEL_DIR, "synthetic_demo_model.keras")
    bootstrap_keras_path = os.path.join(BOOTSTRAP_MODEL_DIR, "bootstrap_model.keras")
    model.save(synth_keras_path)
    model.save(bootstrap_keras_path)
    print(f"\n[+] Saved model to {synth_keras_path} and {bootstrap_keras_path}")

    # 5. Save model metadata
    metadata = {
        "model_architecture": "MobileNetV3-Small",
        "input_width": INPUT_SHAPE[1],
        "input_height": INPUT_SHAPE[0],
        "channels": INPUT_SHAPE[2],
        "model_input_shape": list(INPUT_SHAPE),
        "normalization": "rescaling_0_to_1",
        "color_format": "RGB",
        "class_labels": list(CLASS_LABELS),
        "model_type": "SYNTHETIC_DEMO / BOOTSTRAP",
        "target_validated": False,
        "forensic_status": "PROTOTYPE_DEMO_ONLY_NOT_FORENSICALLY_VALIDATED",
        "training_timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "train_samples": int(len(x_train)),
        "val_samples": int(len(x_val)),
        "val_accuracy": float(history.history["val_accuracy"][-1])
    }

    metadata_path = os.path.join(MODELS_DIR, "model_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[+] Saved model metadata to {metadata_path}")


if __name__ == "__main__":
    main()
