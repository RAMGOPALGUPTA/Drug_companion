# ML Pipeline

image -> quality gate -> calibration -> ROI extraction -> Delta-E -> MobileNetV3 TFLite -> confidence -> arbitration -> final result -> evidence

The current supplied prototype contains bootstrap/synthetic artifacts and is not target-validated.

Runtime model contract:
- 224 x 224
- RGB
- rescaling 0..1
- labels: negative, positive, invalid

The production runtime will verify model artifact hash and metadata before inference.
