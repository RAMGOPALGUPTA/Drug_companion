"""
ML confidence layer for the bundled MobileNetV3-Small INT8 TFLite model.

The rule-based CIEDE2000 engine remains the primary explainable signal.
The ML model corroborates ambiguous results and flags strong disagreement.
"""
from dataclasses import dataclass
from typing import Tuple
import numpy as np

from .config import MLConfidenceConfig

try:
    from ai_edge_litert import interpreter as tflite
    _BACKEND = "ai_edge_litert"
except ImportError:
    try:
        import tflite_runtime.interpreter as tflite
        _BACKEND = "tflite_runtime"
    except ImportError:
        tflite = None
        _BACKEND = None


@dataclass
class MLVerdict:
    label: str
    confidence: float
    raw_scores: Tuple[float, ...]
    backend: str
    model_available: bool
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "raw_scores": tuple(round(s, 4) for s in self.raw_scores),
            "backend": self.backend,
            "model_available": self.model_available,
            "note": self.note,
        }


class TFLiteConfidenceModel:
    """Runtime wrapper for the bundled INT8 MobileNetV3-Small TFLite model."""

    def __init__(self, cfg: MLConfidenceConfig):
        self.cfg = cfg
        self.interpreter = None
        self._input_details = None
        self._output_details = None
        self.load_error = None
        self._load()

    def _load(self):
        if tflite is None:
            self.load_error = "No LiteRT interpreter is installed"
            return

        try:
            self.interpreter = tflite.Interpreter(
                model_path=self.cfg.model_path,
                num_threads=self.cfg.num_threads,
            )
            self.interpreter.allocate_tensors()
            self._input_details = self.interpreter.get_input_details()
            self._output_details = self.interpreter.get_output_details()
        except Exception as exc:
            self.load_error = str(exc)
            self.interpreter = None

    @property
    def is_available(self) -> bool:
        return self.interpreter is not None

    def _quantize_input(self, rgb_float01: np.ndarray) -> np.ndarray:
        detail = self._input_details[0]
        scale, zero_point = detail["quantization"]
        if scale == 0:
            return rgb_float01.astype(detail["dtype"])
        quantized = rgb_float01 / scale + zero_point
        dtype = detail["dtype"]
        qmin, qmax = (0, 255) if dtype == np.uint8 else (-128, 127)
        return np.clip(np.round(quantized), qmin, qmax).astype(dtype)

    def _dequantize_output(self, raw: np.ndarray) -> np.ndarray:
        detail = self._output_details[0]
        scale, zero_point = detail["quantization"]
        if scale == 0:
            return raw.astype(np.float32)
        return (raw.astype(np.float32) - zero_point) * scale

    def predict(self, patch_rgb_uint8: np.ndarray) -> MLVerdict:
        labels = self.cfg.class_labels
        if not self.is_available:
            return MLVerdict(
                label="unavailable",
                confidence=0.0,
                raw_scores=(0.0,) * len(labels),
                backend=_BACKEND or "none",
                model_available=False,
                note=self.load_error or "Model unavailable",
            )

        try:
            resized = _resize_to(patch_rgb_uint8, self.cfg.input_size)
            float01 = resized.astype(np.float32) / 255.0
            quantized = self._quantize_input(float01)
            input_tensor = np.expand_dims(quantized, axis=0)
            self.interpreter.set_tensor(self._input_details[0]["index"], input_tensor)
            self.interpreter.invoke()
            raw_output = self.interpreter.get_tensor(self._output_details[0]["index"])[0]
            scores = _softmax(self._dequantize_output(raw_output))
            best_idx = int(np.argmax(scores))
            best_label = labels[best_idx] if best_idx < len(labels) else f"class_{best_idx}"
            return MLVerdict(
                label=best_label,
                confidence=float(scores[best_idx]),
                raw_scores=tuple(float(s) for s in scores),
                backend=_BACKEND or "none",
                model_available=True,
            )
        except Exception as exc:
            return MLVerdict(
                label="unavailable",
                confidence=0.0,
                raw_scores=(0.0,) * len(labels),
                backend=_BACKEND or "none",
                model_available=False,
                note=f"Inference failed: {exc}",
            )


def _resize_to(img: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
    import cv2
    return cv2.resize(img, size, interpolation=cv2.INTER_AREA)


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    e = np.exp(x)
    return e / e.sum()


def resolve_with_ml(deltae_call: str, ml_verdict: MLVerdict, cfg: MLConfidenceConfig) -> dict:
    result = {
        "rule_based_call": deltae_call,
        "ml_label": ml_verdict.label,
        "ml_confidence": ml_verdict.confidence,
        "final_call": deltae_call,
        "resolution": "rule_based_confident",
        "flagged_for_review": False,
    }

    if not ml_verdict.model_available:
        if deltae_call == "inconclusive":
            result["final_call"] = "inconclusive"
            result["resolution"] = "ml_unavailable_remains_inconclusive"
            result["flagged_for_review"] = True
        return result

    if deltae_call == "inconclusive":
        if ml_verdict.confidence >= cfg.min_confidence and ml_verdict.label in ("positive", "negative"):
            result["final_call"] = ml_verdict.label
            result["resolution"] = "resolved_by_ml_confidence"
        else:
            result["final_call"] = "inconclusive"
            result["resolution"] = "ml_confidence_insufficient"
            result["flagged_for_review"] = True
    else:
        ml_disagrees = (
            ml_verdict.label in ("positive", "negative")
            and ml_verdict.label != deltae_call
            and ml_verdict.confidence >= (cfg.min_confidence + cfg.max_disagreement_margin)
        )
        if ml_disagrees:
            result["resolution"] = "rule_ml_disagreement"
            result["flagged_for_review"] = True

    return result
