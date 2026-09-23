# ML Pipeline

image -> quality gate -> calibration -> ROI -> CIEDE2000 -> MobileNetV3 TFLite -> confidence -> arbitration -> evidence

Input: 224x224 RGB, rescaling 0..1.
Labels: negative, positive, invalid.

The supplied prototype artifact is not target-validated.
