"""
ML confidence layer: MobileNetV3-Small (int8 quantized, TFLite) secondary
classifier used only to arbitrate the ambiguous Delta-E band and to
provide a corroborating/contradicting confidence signal for the evidence
record. This layer never overrides a *confident* Delta-E call on its own;
it only resolves "inconclusive" verdicts and flags disagreement.

Design note: keeping the rule-based engine primary and the ML model
secondary/advisory is a deliberate choice for evidentiary explainability
— the rule-based path is fully traceable to a documented formula (CIEDE2000)
and reference values, whereas the ML path is treated as a corroborating
signal, not the basis of the call, unless explicitly configured otherwise.
"""
from dataclasses import dataclass
from typing import Tuple, Optional
import numpy as np

from .config import MLConfidenceConfig

try:
    import tflite_runtime.interpreter as tflite
    _BACKEND = "tflite_runtime"
except ImportError:
    try:
        import tensorflow as tf
        tflite = tf.lite
        _BACKEND = "tensorflow"
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
    """Thin wrapper around a TFLite Interpreter for int8 MobileNetV3-Small."""

    def __init__(self, cfg: MLConfidenceConfig):
        self.cfg = cfg
        self.interpreter = None
        self._input_details = None
        self._output_details = None
        self._load()

    def _load(self):
        if tflite is None:
            return
        # Attempt loading with BUILTIN_WITHOUT_DEFAULT_DELEGATES first to avoid Windows XNNPack crashes on quantized models
        op_resolver = getattr(getattr(tflite, "experimental", None), "OpResolverType", None)
        interp = None
        if op_resolver is not None and hasattr(op_resolver, "BUILTIN_WITHOUT_DEFAULT_DELEGATES"):
            try:
                interp = tflite.Interpreter(
                    model_path=self.cfg.model_path,
                    num_threads=self.cfg.num_threads,
                    experimental_op_resolver_type=op_resolver.BUILTIN_WITHOUT_DEFAULT_DELEGATES
                )
                interp.allocate_tensors()
            except Exception:
                interp = None

        if interp is None:
            try:
                interp = tflite.Interpreter(
                    model_path=self.cfg.model_path, num_threads=self.cfg.num_threads
                )
                interp.allocate_tensors()
            except Exception:
                interp = None

        if interp is not None:
            self.interpreter = interp
            self._input_details = self.interpreter.get_input_details()
            self._output_details = self.interpreter.get_output_details()
        else:
            self.interpreter = None

    @property
    def is_available(self) -> bool:
        return self.interpreter is not None

    def _quantize_input(self, rgb_float01: np.ndarray) -> np.ndarray:
        """Apply the model's int8 quantization params to a [0,1] float image."""
        detail = self._input_details[0]
        scale, zero_point = detail["quantization"]
        if scale == 0:
            return rgb_float01.astype(detail["dtype"])
        quantized = rgb_float01 / scale + zero_point
        dtype = detail["dtype"]
        qmin, qmax = (0, 255) if dtype == np.uint8 else (-128, 127)
        quantized = np.clip(np.round(quantized), qmin, qmax)
        return quantized.astype(dtype)

    def _dequantize_output(self, raw: np.ndarray) -> np.ndarray:
        detail = self._output_details[0]
        scale, zero_point = detail["quantization"]
        if scale == 0:
            return raw.astype(np.float32)
        return (raw.astype(np.float32) - zero_point) * scale

    def predict(self, patch_rgb_uint8: np.ndarray) -> MLVerdict:
        """
        Run inference on a single 224x224x3 RGB uint8 patch.
        Returns an MLVerdict; if the model isn't available, returns a
        clearly-flagged fallback verdict rather than raising, so the
        pipeline can proceed to human review.
        """
        labels = self.cfg.class_labels

        if not self.is_available:
            return MLVerdict(
                label="unavailable", confidence=0.0, raw_scores=(0.0,) * len(labels),
                backend=_BACKEND or "none", model_available=False,
                note="TFLite model not loaded; ML confidence layer skipped. "
                     "Result relies on rule-based Delta-E engine only.",
            )

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
            label=best_label, confidence=float(scores[best_idx]),
            raw_scores=tuple(float(s) for s in scores),
            backend=_BACKEND, model_available=True,
        )


def _resize_to(img: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
    import cv2
    return cv2.resize(img, size, interpolation=cv2.INTER_AREA)


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    e = np.exp(x)
    return e / e.sum()


def resolve_with_ml(deltae_call: str, ml_verdict: MLVerdict,
                     cfg: MLConfidenceConfig) -> dict:
    """
    Combine the Delta-E rule-based call with the ML verdict into a final
    decision + audit trail. Rule-based confident calls are only flagged
    (not overridden) if ML strongly disagrees; inconclusive rule-based
    calls are resolved by ML confidence if it clears min_confidence.
    """
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
        # Rule-based was confident; check for strong ML disagreement.
        ml_disagrees = (
            ml_verdict.label in ("positive", "negative")
            and ml_verdict.label != deltae_call
            and ml_verdict.confidence >= (cfg.min_confidence + cfg.max_disagreement_margin)
        )
        if ml_disagrees:
            result["resolution"] = "rule_ml_disagreement"
            result["flagged_for_review"] = True
            # Final call intentionally stays rule-based per design note above.

    return result
