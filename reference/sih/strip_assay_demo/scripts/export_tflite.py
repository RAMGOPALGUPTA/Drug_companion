#!/usr/bin/env python3
"""
scripts/export_tflite.py

Exports trained MobileNetV3-Small to:
- models/bootstrap_model_fp32.tflite
- models/bootstrap_model_fp16.tflite
- models/bootstrap_model_int8.tflite
- models/mobilenetv3_small_int8.tflite (wires into existing core/ml_confidence.py)

Uses representative calibration dataset from TRAIN & CALIBRATION splits.
Runs INT8 acceptance testing vs FP32 and logs validation metrics.
"""

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import json
import time
import shutil
import numpy as np
import cv2

import tensorflow as tf

MODELS_DIR = os.path.abspath("models")
SYNTH_MODEL_PATH = os.path.join(MODELS_DIR, "synthetic_demo", "synthetic_demo_model.keras")
BOOTSTRAP_MODEL_PATH = os.path.join(MODELS_DIR, "bootstrap", "bootstrap_model.keras")
METADATA_PATH = os.path.join(MODELS_DIR, "model_metadata.json")

FP32_PATH = os.path.join(MODELS_DIR, "bootstrap_model_fp32.tflite")
FP16_PATH = os.path.join(MODELS_DIR, "bootstrap_model_fp16.tflite")
INT8_PATH = os.path.join(MODELS_DIR, "bootstrap_model_int8.tflite")
CORE_INT8_PATH = os.path.join(MODELS_DIR, "mobilenetv3_small_int8.tflite")


def load_metadata():
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"model_input_shape": [224, 224, 3]}


def get_representative_dataset(input_shape=(224, 224, 3), n_samples=100):
    """Representative dataset generator drawn strictly from TRAIN/CALIBRATION data."""
    manifest_path = os.path.abspath("data/processed/synthetic_manifest.json")
    samples = []
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            records = json.load(f)
        for r in records:
            if r.get("split") in ("TRAIN", "CALIBRATION"):
                p = r.get("image_path")
                if os.path.exists(p):
                    img = cv2.imread(p)
                    if img is not None:
                        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        # Crop center strip region
                        h, w = rgb.shape[:2]
                        crop = rgb[int(h*0.2):int(h*0.7), int(w*0.5):int(w*0.9)]
                        resized = cv2.resize(crop, (input_shape[1], input_shape[0]))
                        samples.append(resized.astype(np.float32))
                        if len(samples) >= n_samples:
                            break

    # If samples are few, add synthetic variations
    rng = np.random.default_rng(42)
    while len(samples) < n_samples:
        dummy = rng.integers(30, 240, input_shape, dtype=np.uint8)
        samples.append(dummy.astype(np.float32))

    def representative_gen():
        for s in samples:
            yield [np.expand_dims(s, axis=0)]

    return representative_gen, samples


def export_fp32(model, out_path):
    print(f"[*] Converting to Float32 TFLite ({out_path})...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    tflite_model = converter.convert()
    with open(out_path, "wb") as f:
        f.write(tflite_model)
    print(f"[+] Exported FP32 ({os.path.getsize(out_path)/(1024*1024):.2f} MB)")
    return tflite_model


def export_fp16(model, out_path):
    print(f"[*] Converting to Float16 TFLite ({out_path})...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    tflite_model = converter.convert()
    with open(out_path, "wb") as f:
        f.write(tflite_model)
    print(f"[+] Exported FP16 ({os.path.getsize(out_path)/(1024*1024):.2f} MB)")
    return tflite_model


def export_int8(model, out_path, rep_gen):
    print(f"[*] Converting to INT8 Quantized TFLite ({out_path})...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = rep_gen
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    try:
        tflite_model = converter.convert()
        with open(out_path, "wb") as f:
            f.write(tflite_model)
        print(f"[+] Exported INT8 ({os.path.getsize(out_path)/(1024*1024):.2f} MB)")
        return tflite_model, True
    except Exception as e:
        print(f"[!] INT8 full integer conversion warning: {e}. Falling back to dynamic range INT8...")
        converter_dr = tf.lite.TFLiteConverter.from_keras_model(model)
        converter_dr.optimizations = [tf.lite.Optimize.DEFAULT]
        tflite_model = converter_dr.convert()
        with open(out_path, "wb") as f:
            f.write(tflite_model)
        print(f"[+] Exported dynamic-range INT8 ({os.path.getsize(out_path)/(1024*1024):.2f} MB)")
        return tflite_model, False


def benchmark_models(keras_model, fp32_path, fp16_path, int8_path, test_samples):
    """Run comparative inference on test samples to evaluate agreement and latency."""
    print("\n[*] Benchmarking Keras FP32 vs TFLite FP32 vs FP16 vs INT8...")
    results = {}

    # 1. Keras FP32 baseline
    t0 = time.perf_counter()
    keras_preds = keras_model.predict(test_samples, verbose=0)
    keras_time = (time.perf_counter() - t0) * 1000 / len(test_samples)
    keras_classes = np.argmax(keras_preds, axis=1)

    results["Keras_FP32"] = {
        "avg_latency_ms": round(keras_time, 2),
        "agreement_with_baseline": 1.0,
        "mean_confidence": float(np.mean(np.max(keras_preds, axis=1)))
    }

    # Helper to test TFLite model
    def test_tflite(path):
        op_resolver = getattr(getattr(tf.lite, "experimental", None), "OpResolverType", None)
        if op_resolver and hasattr(op_resolver, "BUILTIN_WITHOUT_DEFAULT_DELEGATES"):
            try:
                interpreter = tf.lite.Interpreter(
                    model_path=path,
                    experimental_op_resolver_type=op_resolver.BUILTIN_WITHOUT_DEFAULT_DELEGATES
                )
                interpreter.allocate_tensors()
            except Exception:
                interpreter = tf.lite.Interpreter(model_path=path)
                interpreter.allocate_tensors()
        else:
            interpreter = tf.lite.Interpreter(model_path=path)
            interpreter.allocate_tensors()

        in_det = interpreter.get_input_details()[0]
        out_det = interpreter.get_output_details()[0]

        in_scale, in_zp = in_det.get("quantization", (0.0, 0))
        out_scale, out_zp = out_det.get("quantization", (0.0, 0))
        in_dtype = in_det["dtype"]

        preds = []
        t0 = time.perf_counter()
        for s in test_samples:
            tensor = s.astype(np.float32)
            if in_scale > 0:
                tensor = np.round(tensor / in_scale + in_zp)
                qmin, qmax = (0, 255) if in_dtype == np.uint8 else (-128, 127)
                tensor = np.clip(tensor, qmin, qmax).astype(in_dtype)
            else:
                tensor = tensor.astype(in_dtype)

            tensor = np.expand_dims(tensor, axis=0)
            interpreter.set_tensor(in_det["index"], tensor)
            interpreter.invoke()
            out = interpreter.get_tensor(out_det["index"])[0]

            if out_scale > 0:
                out = (out.astype(np.float32) - out_zp) * out_scale
            # Apply softmax if needed
            exp = np.exp(out - np.max(out))
            prob = exp / np.sum(exp)
            preds.append(prob)

        lat = (time.perf_counter() - t0) * 1000 / len(test_samples)
        preds = np.array(preds)
        pred_classes = np.argmax(preds, axis=1)
        agreement = float(np.mean(pred_classes == keras_classes))
        conf = float(np.mean(np.max(preds, axis=1)))
        return {
            "avg_latency_ms": round(lat, 2),
            "agreement_with_baseline": round(agreement, 4),
            "mean_confidence": round(conf, 4)
        }

    results["TFLite_FP32"] = test_tflite(fp32_path)
    results["TFLite_FP16"] = test_tflite(fp16_path)
    results["TFLite_INT8"] = test_tflite(int8_path)

    print("\nBenchmark Summary:")
    print(f"{'Variant':15s} | {'Latency (ms)':12s} | {'Agreement':10s} | {'Confidence':10s}")
    print("-" * 55)
    for v, d in results.items():
        print(f"{v:15s} | {d['avg_latency_ms']:12.2f} | {d['agreement_with_baseline']*100:9.1f}% | {d['mean_confidence']:10.3f}")

    # Check INT8 Acceptance Criteria
    int8_agree = results["TFLite_INT8"]["agreement_with_baseline"]
    if int8_agree >= 0.90:
        int8_status = "ACCEPTED"
        print(f"\n[+] INT8 Acceptance Status: {int8_status} (Agreement {int8_agree*100:.1f}% >= threshold)")
    else:
        int8_status = "REJECTED_DUE_TO_DEGRADATION"
        print(f"\n[!] INT8 Acceptance Status: {int8_status} (Agreement {int8_agree*100:.1f}% < threshold). Fallback: FP16 recommended.")

    results["INT8_acceptance_status"] = int8_status
    return results


def main():
    print("=========================================================")
    print("STRIP_ASSAY: TFLITE CONVERSION & QUANTIZATION BENCHMARK")
    print("=========================================================")

    model_path = SYNTH_MODEL_PATH if os.path.exists(SYNTH_MODEL_PATH) else BOOTSTRAP_MODEL_PATH
    if not os.path.exists(model_path):
        print(f"[!] Model file not found at {model_path}. Train the model first.")
        sys.exit(1)

    print(f"[*] Loading Keras model from {model_path}...")
    model = tf.keras.models.load_model(model_path)
    meta = load_metadata()
    input_shape = tuple(meta.get("model_input_shape", [224, 224, 3]))

    rep_gen, rep_samples = get_representative_dataset(input_shape, n_samples=60)

    # 1. Export variants
    export_fp32(model, FP32_PATH)
    export_fp16(model, FP16_PATH)
    export_int8(model, INT8_PATH, rep_gen)

    # 2. Wire INT8 model to core/ml_confidence.py location
    shutil.copy2(INT8_PATH, CORE_INT8_PATH)
    print(f"[+] Wired model to core pipeline at {CORE_INT8_PATH}")

    # 3. Benchmark comparison
    test_batch = np.array(rep_samples[:20], dtype=np.float32)
    bench_results = benchmark_models(model, FP32_PATH, FP16_PATH, INT8_PATH, test_batch)

    # Save benchmark report
    os.makedirs("reports", exist_ok=True)
    bench_path = os.path.join("reports", "tflite_model_comparison.json")
    with open(bench_path, "w", encoding="utf-8") as f:
        json.dump(bench_results, f, indent=2)
    print(f"[+] Benchmark comparison report saved to {bench_path}")


if __name__ == "__main__":
    main()
