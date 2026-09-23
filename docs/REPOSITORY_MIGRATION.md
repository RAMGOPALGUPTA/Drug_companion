# Repository Migration

The previous Sih repository is treated as a source/reference repository.

Useful existing material to migrate:
- frontend
- mobile
- dashboard
- ml workspace
- strip assay prototype
- model metadata and TFLite artifact
- quality gate
- calibration
- ROI extraction
- Delta-E
- ML confidence/arbitration
- evidence packet logic

Migration rule: copy source code after the new architecture is established. Do not copy the old backend structure wholesale.

The new backend is the canonical application runtime.
