"""Export a trained Keras model to a compressed TensorFlow Lite asset."""

import argparse
from pathlib import Path

import tensorflow as tf


parser = argparse.ArgumentParser()
parser.add_argument("--model", required=True)
parser.add_argument("--output", required=True)
arguments = parser.parse_args()

output = Path(arguments.output)
output.parent.mkdir(parents=True, exist_ok=True)
model = tf.keras.models.load_model(arguments.model)
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
output.write_bytes(converter.convert())
print(output)
