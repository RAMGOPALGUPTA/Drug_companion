"""
Central configuration for the colorimetric assay pipeline.

All tunable thresholds live here so Phase 12 (kit-specific tuning) only
requires editing this one file rather than hunting through the pipeline.
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class QualityGateConfig:
    # Laplacian variance below this => image considered too blurry
    blur_variance_threshold: float = 100.0
    # Mean luminance (0-255) acceptable range for exposure
    min_mean_luminance: float = 40.0
    max_mean_luminance: float = 215.0
    # Fraction of pixels allowed to be clipped (over/under exposed)
    max_clipped_fraction: float = 0.03
    # Minimum sharp-edge coverage of the reference card region
    min_card_edge_density: float = 0.02


@dataclass
class CalibrationConfig:
    # Expected reference card patch layout: name -> (row, col) in a grid
    reference_grid_shape: Tuple[int, int] = (4, 6)
    # sRGB ground-truth values (0-255) for each named reference patch,
    # e.g. from an X-Rite/Spyder-style calibration card or a printed
    # kit-specific reference strip. Replace with your card's certified
    # values during Phase 12 tuning.
    reference_patches: Dict[str, Tuple[int, int, int]] = field(default_factory=lambda: {
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
    })
    # Max acceptable residual (mean absolute error, sRGB units) after
    # fitting the 3x3 matrix; above this the calibration itself is untrusted.
    max_fit_residual: float = 6.0


@dataclass
class DeltaEConfig:
    # CIEDE2000 distance below which a reagent-pad color is a confident match
    confident_match_threshold: float = 4.0
    # Above this distance, the pad is confidently NOT a match
    confident_nonmatch_threshold: float = 12.0
    # Between confident_match and confident_nonmatch => "inconclusive" band,
    # deferred to the ML confidence layer / human review.
    # Reference reagent-endpoint colors (Lab) per analyte, populated from
    # kit manufacturer data or empirical calibration. Placeholder values.
    analyte_reference_lab: Dict[str, Tuple[float, float, float]] = field(default_factory=lambda: {
        "opioid_positive": (45.0, 45.0, 15.0),
        "opioid_negative": (70.0, 0.0, 5.0),
        "stimulant_positive": (55.0, 30.0, -40.0),
        "stimulant_negative": (70.0, 0.0, 5.0),
        "benzo_positive": (50.0, -10.0, 40.0),
        "benzo_negative": (70.0, 0.0, 5.0),
    })


@dataclass
class MLConfidenceConfig:
    model_path: str = "models/mobilenetv3_small_int8.tflite"
    input_size: Tuple[int, int] = (224, 224)
    num_threads: int = 2
    # Softmax confidence below this => defer to "inconclusive"
    min_confidence: float = 0.65
    # If rule-based (Delta-E) and ML disagree on class by more than this
    # margin, flag for human review regardless of individual confidences.
    max_disagreement_margin: float = 0.30
    class_labels: Tuple[str, ...] = ("negative", "positive", "invalid")


@dataclass
class EvidenceConfig:
    output_dir: str = "evidence_packets"
    hash_algorithm: str = "sha256"
    # Include full-resolution source image bytes in the packet (vs. just hash)
    embed_source_image: bool = True
    schema_version: str = "1.0.0"


@dataclass
class PipelineConfig:
    quality_gate: QualityGateConfig = field(default_factory=QualityGateConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    delta_e: DeltaEConfig = field(default_factory=DeltaEConfig)
    ml_confidence: MLConfidenceConfig = field(default_factory=MLConfidenceConfig)
    evidence: EvidenceConfig = field(default_factory=EvidenceConfig)


DEFAULT_CONFIG = PipelineConfig()
