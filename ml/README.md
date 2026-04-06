# ML Workspace

This directory is the entry point for the Chicago crashes ML pipeline.

## Structure

- `plans/`: planning docs, milestones, contracts, and operating procedures.
- `sql/`: SQL assets for curated ML-ready datasets and prediction outputs.
- `src/`: Python pipeline scripts for extract, feature engineering, training, evaluation, and scoring.
- `configs/`: model and policy configuration files.
- `artifacts/`: model binaries, calibration artifacts, and metadata JSON outputs.

## Recommended Execution Order

1. Finalize planning docs in `plans/`.
2. Build base and feature tables with `sql/` and `src/data_extract.py`.
3. Train models with `src/train_severity.py` and `src/train_hotspot.py`.
4. Evaluate and calibrate with `src/evaluate.py`.
5. Generate production scores with `src/score.py` and SQL prediction outputs.
