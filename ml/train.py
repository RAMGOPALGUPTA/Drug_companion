"""Train the field-test image classifier from real, labelled operator images.

This script intentionally refuses to train a model from incomplete class data or
from too few samples. It does not manufacture examples or publish an accuracy
claim when no evidence data has been provided.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, UnidentifiedImageError
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
import tensorflow as tf


LABELS = ("negative", "positive", "inconclusive")
IMAGE_SIZE = (224, 224)
MINIMUM_IMAGES_PER_CLASS = 5
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def image_paths(directory: Path) -> Iterable[Path]:
    return (path for path in sorted(directory.rglob("*")) if path.is_file() and path.suffix.lower() in VALID_EXTENSIONS)


def load_dataset(data_directory: Path) -> tuple[np.ndarray, np.ndarray, dict[str, int], list[str]]:
    images: list[np.ndarray] = []
    targets: list[int] = []
    unreadable: list[str] = []
    counts: Counter[str] = Counter()

    for index, label in enumerate(LABELS):
        label_directory = data_directory / label
        if not label_directory.is_dir():
            continue
        for path in image_paths(label_directory):
            try:
                with Image.open(path) as source:
                    image = source.convert("RGB").resize(IMAGE_SIZE)
                    images.append(np.asarray(image, dtype=np.float32) / 255.0)
                targets.append(index)
                counts[label] += 1
            except (UnidentifiedImageError, OSError, ValueError):
                unreadable.append(str(path))

    missing = [label for label in LABELS if counts[label] < MINIMUM_IMAGES_PER_CLASS]
    if missing:
        details = ", ".join(f"{label} ({counts[label]}/{MINIMUM_IMAGES_PER_CLASS})" for label in missing)
        raise ValueError(f"At least {MINIMUM_IMAGES_PER_CLASS} readable images are required for every class: {details}")
    return np.asarray(images), np.asarray(targets), dict(counts), unreadable


def build_model() -> tf.keras.Model:
    return tf.keras.Sequential([
        tf.keras.layers.Input(shape=(*IMAGE_SIZE, 3)),
        tf.keras.layers.Conv2D(16, 3, activation="relu"),
        tf.keras.layers.MaxPooling2D(),
        tf.keras.layers.Conv2D(32, 3, activation="relu"),
        tf.keras.layers.MaxPooling2D(),
        tf.keras.layers.Conv2D(64, 3, activation="relu"),
        tf.keras.layers.GlobalAveragePooling2D(),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.Dense(len(LABELS), activation="softmax"),
    ])


def write_json(path: Path, document: dict) -> None:
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the SIH field-test image classifier.")
    parser.add_argument("--data", default="dataset/raw", help="Directory containing negative/, positive/, and inconclusive/.")
    parser.add_argument("--output", default="artifacts", help="Directory for model and validation artifacts.")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    arguments = parser.parse_args()
    if arguments.epochs < 1 or arguments.batch_size < 1:
        raise SystemExit("--epochs and --batch-size must be positive integers")

    np.random.seed(arguments.seed)
    tf.keras.utils.set_random_seed(arguments.seed)
    output_directory = Path(arguments.output)
    output_directory.mkdir(parents=True, exist_ok=True)

    try:
        images, targets, counts, unreadable = load_dataset(Path(arguments.data))
    except ValueError as error:
        raise SystemExit(f"Dataset validation failed: {error}") from error

    train_images, validation_images, train_targets, validation_targets = train_test_split(
        images, targets, test_size=0.2, random_state=arguments.seed, stratify=targets,
    )
    model = build_model()
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    history = model.fit(
        train_images,
        train_targets,
        validation_data=(validation_images, validation_targets),
        epochs=arguments.epochs,
        batch_size=arguments.batch_size,
        callbacks=[tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)],
        verbose=2,
    )

    probabilities = model.predict(validation_images, verbose=0)
    predictions = probabilities.argmax(axis=1)
    validation_loss, validation_accuracy = model.evaluate(validation_images, validation_targets, verbose=0)
    model.save(output_directory / "model.keras")
    write_json(output_directory / "labels.json", {"labels": list(LABELS), "image_size": list(IMAGE_SIZE)})
    write_json(output_directory / "metrics.json", {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_class_counts": counts,
        "training_samples": int(len(train_targets)),
        "validation_samples": int(len(validation_targets)),
        "unreadable_files": unreadable,
        "validation_loss": float(validation_loss),
        "validation_accuracy": float(validation_accuracy),
        "classification_report": classification_report(validation_targets, predictions, labels=range(len(LABELS)), target_names=LABELS, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(validation_targets, predictions, labels=range(len(LABELS))).tolist(),
        "epochs_completed": len(history.history["loss"]),
    })
    print(f"Saved model and validation report to {output_directory}")


if __name__ == "__main__":
    main()
