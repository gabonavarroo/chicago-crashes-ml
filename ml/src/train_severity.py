"""Train severity classifiers with time-aware validation and calibration."""

from __future__ import annotations

import argparse
import itertools
import json
import pickle
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, f1_score, log_loss

EPSILON = 1e-6


@dataclass(frozen=True)
class SearchResult:
    params: dict[str, Any]
    fold_count: int
    mean_log_loss: float
    mean_macro_f1: float
    mean_weighted_f1: float
    mean_brier: float
    mean_ece: float


def parse_args() -> argparse.Namespace:
    root_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Train severity model with baseline and boosted candidate."
    )
    parser.add_argument(
        "--feature-root",
        type=Path,
        default=root_dir / "artifacts" / "features",
        help="Base directory containing transformed feature artifacts.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=root_dir / "artifacts" / "models" / "severity",
        help="Output base directory for model artifacts.",
    )
    parser.add_argument(
        "--snapshot-version",
        type=str,
        default="v1",
        help="Feature snapshot version under feature-root.",
    )
    parser.add_argument(
        "--extraction-date",
        type=str,
        default=None,
        help="Extraction date (YYYY-MM-DD). If omitted, latest available is used.",
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        default="severity",
        help="Dataset directory name under the resolved feature run directory.",
    )
    parser.add_argument(
        "--model-family",
        choices=["auto", "xgboost", "catboost"],
        default="auto",
        help="Primary boosted model family. 'auto' prefers XGBoost then CatBoost.",
    )
    parser.add_argument(
        "--calibration-method",
        choices=["isotonic", "platt"],
        default="isotonic",
        help="Probability calibration method fitted on the validation split.",
    )
    parser.add_argument(
        "--logreg-c",
        type=float,
        default=1.0,
        help="Inverse regularization strength for baseline logistic regression.",
    )
    parser.add_argument(
        "--search-iterations",
        type=int,
        default=20,
        help="Number of random hyperparameter candidates for primary model.",
    )
    parser.add_argument(
        "--time-splits",
        type=int,
        default=4,
        help="Number of forward-chaining folds for time-aware search.",
    )
    parser.add_argument(
        "--min-train-fraction",
        type=float,
        default=0.5,
        help="Minimum chronological fraction reserved for fold training window.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Global random seed.",
    )
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=-1,
        help="Worker threads for model fitting where supported.",
    )
    return parser.parse_args()


def resolve_feature_run_dir(feature_root: Path, version: str, extraction_date: str | None) -> Path:
    version_dir = feature_root / f"version={version}"
    if not version_dir.exists():
        raise FileNotFoundError(f"Feature version directory not found: {version_dir}")

    if extraction_date:
        selected = version_dir / f"extraction_date={extraction_date}"
        if not selected.exists():
            raise FileNotFoundError(f"Feature extraction directory not found: {selected}")
        return selected

    candidates = sorted(
        [path for path in version_dir.glob("extraction_date=*") if path.is_dir()],
        key=lambda path: path.name,
    )
    if not candidates:
        raise FileNotFoundError(f"No extraction directories found under: {version_dir}")
    return candidates[-1]


def load_split_dataset(dataset_dir: Path, split_name: str) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    x_path = dataset_dir / f"X_{split_name}.parquet"
    y_path = dataset_dir / f"y_{split_name}.parquet"
    keys_path = dataset_dir / f"keys_{split_name}.parquet"
    for path in (x_path, y_path, keys_path):
        if not path.exists():
            raise FileNotFoundError(f"Required split artifact not found: {path}")

    x_frame = pd.read_parquet(x_path)
    y_frame = pd.read_parquet(y_path)
    keys_frame = pd.read_parquet(keys_path)
    if y_frame.empty:
        raise ValueError(f"Target frame is empty for split '{split_name}'.")
    target_col = y_frame.columns[0]
    y = coerce_binary_target(y_frame[target_col])
    return x_frame, y, keys_frame


def coerce_binary_target(series: pd.Series) -> np.ndarray:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().any():
        bad_count = int(numeric.isna().sum())
        raise ValueError(
            f"Target contains non-numeric values ({bad_count} rows) and cannot be coerced."
        )
    binary = (numeric.values > 0).astype(int)
    return binary


def select_time_column(keys_frame: pd.DataFrame) -> str:
    candidates = [
        column
        for column in keys_frame.columns
        if "date" in column.lower() or "time" in column.lower()
    ]
    if candidates:
        return candidates[0]
    return keys_frame.columns[-1]


def build_time_aware_folds(
    keys_train: pd.DataFrame,
    y_train: np.ndarray,
    n_splits: int,
    min_train_fraction: float,
) -> list[tuple[np.ndarray, np.ndarray]]:
    if n_splits < 1:
        raise ValueError("--time-splits must be >= 1.")
    if not 0.1 <= min_train_fraction < 1.0:
        raise ValueError("--min-train-fraction must be in [0.1, 1.0).")

    time_column = select_time_column(keys_train)
    timestamps = pd.to_datetime(keys_train[time_column], errors="coerce")
    if timestamps.isna().any():
        bad_count = int(timestamps.isna().sum())
        raise ValueError(
            f"Unable to parse {bad_count} timestamp rows from time column '{time_column}'."
        )

    order = np.argsort(timestamps.values)
    sample_count = len(order)
    min_train_size = max(32, int(sample_count * min_train_fraction))
    min_train_size = min(min_train_size, max(sample_count - 2, 1))
    if min_train_size >= sample_count - 1:
        raise ValueError(
            "Not enough training rows to create time-aware folds. "
            f"Rows: {sample_count}, min_train_size: {min_train_size}."
        )

    fold_points = np.linspace(min_train_size, sample_count, n_splits + 1, dtype=int)
    folds: list[tuple[np.ndarray, np.ndarray]] = []
    for index in range(n_splits):
        train_end = int(fold_points[index])
        valid_end = int(fold_points[index + 1])
        if valid_end - train_end < 2:
            continue
        train_idx = order[:train_end]
        valid_idx = order[train_end:valid_end]
        if len(np.unique(y_train[train_idx])) < 2:
            continue
        if len(np.unique(y_train[valid_idx])) < 2:
            continue
        folds.append((train_idx, valid_idx))

    if not folds:
        raise ValueError(
            "No valid time-aware folds produced with both classes represented. "
            "Try fewer --time-splits or a smaller --min-train-fraction."
        )
    return folds


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, bins: int = 15) -> float:
    clipped = np.clip(y_prob, EPSILON, 1.0 - EPSILON)
    boundaries = np.linspace(0.0, 1.0, bins + 1)
    bucket_idx = np.digitize(clipped, boundaries[1:-1], right=True)
    ece = 0.0
    for bucket in range(bins):
        mask = bucket_idx == bucket
        if not np.any(mask):
            continue
        accuracy = float(np.mean(y_true[mask]))
        confidence = float(np.mean(clipped[mask]))
        weight = float(np.mean(mask))
        ece += abs(accuracy - confidence) * weight
    return float(ece)


def compute_binary_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    clipped = np.clip(y_prob, EPSILON, 1.0 - EPSILON)
    pred = (clipped >= 0.5).astype(int)
    return {
        "macro_f1": float(f1_score(y_true, pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, pred, average="weighted", zero_division=0)),
        "log_loss": float(log_loss(y_true, clipped, labels=[0, 1])),
        "brier": float(brier_score_loss(y_true, clipped)),
        "ece": expected_calibration_error(y_true, clipped),
    }


def sample_hyperparameters(
    search_space: dict[str, list[Any]],
    iterations: int,
    seed: int,
) -> list[dict[str, Any]]:
    keys = sorted(search_space.keys())
    max_combinations = 1
    for key in keys:
        max_combinations *= len(search_space[key])

    if max_combinations <= 0:
        raise ValueError("Search space is empty.")

    if max_combinations <= iterations:
        return [dict(zip(keys, values)) for values in itertools.product(*(search_space[k] for k in keys))]

    rng = random.Random(seed)
    chosen: dict[tuple[Any, ...], dict[str, Any]] = {}
    max_attempts = max(100, iterations * 30)
    attempts = 0
    while len(chosen) < iterations and attempts < max_attempts:
        attempts += 1
        params = {key: rng.choice(search_space[key]) for key in keys}
        signature = tuple(params[key] for key in keys)
        if signature not in chosen:
            chosen[signature] = params
    return list(chosen.values())


def _import_xgboost() -> Any | None:
    try:
        import xgboost as xgb
    except ImportError:
        return None
    return xgb


def _import_catboost() -> Any | None:
    try:
        from catboost import CatBoostClassifier
    except ImportError:
        return None
    return CatBoostClassifier


def resolve_primary_family(preference: str) -> str:
    xgb = _import_xgboost()
    cat = _import_catboost()
    available: dict[str, bool] = {"xgboost": xgb is not None, "catboost": cat is not None}

    if preference == "auto":
        if available["xgboost"]:
            return "xgboost"
        if available["catboost"]:
            return "catboost"
    elif available.get(preference):
        return preference

    missing = []
    if not available["xgboost"]:
        missing.append("xgboost")
    if not available["catboost"]:
        missing.append("catboost")
    missing_text = ", ".join(missing) if missing else "none"
    raise ImportError(
        "No supported boosted model package is available for severity training. "
        f"Requested='{preference}', missing packages: {missing_text}."
    )


def build_xgboost_classifier(
    params: dict[str, Any],
    class_ratio: float,
    seed: int,
    n_jobs: int,
) -> Any:
    xgb = _import_xgboost()
    if xgb is None:
        raise ImportError("xgboost package is not installed.")
    return xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=seed,
        tree_method="hist",
        n_jobs=n_jobs,
        scale_pos_weight=class_ratio,
        **params,
    )


def build_catboost_classifier(
    params: dict[str, Any],
    class_ratio: float,
    seed: int,
    n_jobs: int,
) -> Any:
    cat = _import_catboost()
    if cat is None:
        raise ImportError("catboost package is not installed.")
    return cat(
        loss_function="Logloss",
        eval_metric="Logloss",
        random_seed=seed,
        class_weights=[1.0, class_ratio],
        verbose=False,
        thread_count=n_jobs if n_jobs > 0 else -1,
        **params,
    )


def build_primary_model(
    family: str,
    params: dict[str, Any],
    class_ratio: float,
    seed: int,
    n_jobs: int,
) -> Any:
    if family == "xgboost":
        return build_xgboost_classifier(params=params, class_ratio=class_ratio, seed=seed, n_jobs=n_jobs)
    if family == "catboost":
        return build_catboost_classifier(params=params, class_ratio=class_ratio, seed=seed, n_jobs=n_jobs)
    raise ValueError(f"Unsupported family: {family}")


def predicted_positive_proba(model: Any, x_frame: pd.DataFrame) -> np.ndarray:
    if not hasattr(model, "predict_proba"):
        raise ValueError(f"Model {type(model).__name__} does not implement predict_proba.")
    probabilities = model.predict_proba(x_frame)
    if probabilities.ndim != 2 or probabilities.shape[1] < 2:
        raise ValueError(
            f"Unexpected probability output shape from {type(model).__name__}: {probabilities.shape}"
        )
    return np.asarray(probabilities[:, 1], dtype=float)


def positive_class_ratio(y_train: np.ndarray) -> float:
    positives = int(np.sum(y_train == 1))
    negatives = int(np.sum(y_train == 0))
    if positives == 0:
        raise ValueError("Training split has no positive class rows.")
    return float(max(negatives, 1) / max(positives, 1))


def search_primary_model(
    family: str,
    x_train: pd.DataFrame,
    y_train: np.ndarray,
    folds: list[tuple[np.ndarray, np.ndarray]],
    iterations: int,
    seed: int,
    n_jobs: int,
) -> tuple[dict[str, Any], list[SearchResult]]:
    if family == "xgboost":
        space = {
            "n_estimators": [250, 400, 600, 800],
            "max_depth": [3, 4, 6, 8],
            "learning_rate": [0.03, 0.05, 0.08, 0.12],
            "subsample": [0.7, 0.85, 1.0],
            "colsample_bytree": [0.7, 0.85, 1.0],
            "min_child_weight": [1, 3, 7],
            "reg_lambda": [1.0, 3.0, 6.0, 10.0],
        }
    elif family == "catboost":
        space = {
            "iterations": [300, 500, 700, 900],
            "depth": [4, 6, 8, 10],
            "learning_rate": [0.02, 0.04, 0.06, 0.1],
            "l2_leaf_reg": [2.0, 4.0, 8.0, 12.0],
            "random_strength": [0.0, 0.5, 1.0],
            "bagging_temperature": [0.0, 0.5, 1.0],
        }
    else:
        raise ValueError(f"Unsupported model family for search: {family}")

    candidates = sample_hyperparameters(search_space=space, iterations=iterations, seed=seed)
    class_ratio = positive_class_ratio(y_train)
    results: list[SearchResult] = []

    for candidate_id, params in enumerate(candidates):
        fold_metrics: list[dict[str, float]] = []
        for fold_id, (fold_train_idx, fold_valid_idx) in enumerate(folds):
            model_seed = seed + candidate_id * 100 + fold_id
            model = build_primary_model(
                family=family,
                params=params,
                class_ratio=class_ratio,
                seed=model_seed,
                n_jobs=n_jobs,
            )
            model.fit(x_train.iloc[fold_train_idx], y_train[fold_train_idx])
            probabilities = predicted_positive_proba(model, x_train.iloc[fold_valid_idx])
            metrics = compute_binary_metrics(y_train[fold_valid_idx], probabilities)
            fold_metrics.append(metrics)

        if not fold_metrics:
            continue
        results.append(
            SearchResult(
                params=params,
                fold_count=len(fold_metrics),
                mean_log_loss=float(np.mean([m["log_loss"] for m in fold_metrics])),
                mean_macro_f1=float(np.mean([m["macro_f1"] for m in fold_metrics])),
                mean_weighted_f1=float(np.mean([m["weighted_f1"] for m in fold_metrics])),
                mean_brier=float(np.mean([m["brier"] for m in fold_metrics])),
                mean_ece=float(np.mean([m["ece"] for m in fold_metrics])),
            )
        )

    if not results:
        raise RuntimeError("Hyperparameter search produced no valid candidates.")

    ranked = sorted(
        results,
        key=lambda item: (
            item.mean_log_loss,
            item.mean_brier,
            item.mean_ece,
            -item.mean_macro_f1,
            -item.mean_weighted_f1,
        ),
    )
    return ranked[0].params, ranked


def fit_baseline_model(x_train: pd.DataFrame, y_train: np.ndarray, c_value: float, seed: int) -> LogisticRegression:
    model = LogisticRegression(
        penalty="l2",
        C=c_value,
        class_weight="balanced",
        solver="lbfgs",
        max_iter=2000,
        random_state=seed,
    )
    model.fit(x_train, y_train)
    return model


def fit_calibrator(
    method: str,
    raw_scores: np.ndarray,
    y_true: np.ndarray,
    seed: int,
) -> dict[str, Any]:
    if len(np.unique(y_true)) < 2:
        raise ValueError(
            "Validation target contains one class only; cannot fit isotonic/platt calibrator."
        )
    if method == "isotonic":
        model = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        model.fit(raw_scores, y_true)
        return {"method": method, "model": model}
    if method == "platt":
        model = LogisticRegression(
            penalty="l2",
            C=1.0,
            solver="lbfgs",
            class_weight="balanced",
            random_state=seed,
            max_iter=2000,
        )
        model.fit(raw_scores.reshape(-1, 1), y_true)
        return {"method": method, "model": model}
    raise ValueError(f"Unsupported calibration method: {method}")


def apply_calibrator(calibrator_bundle: dict[str, Any], raw_scores: np.ndarray) -> np.ndarray:
    method = calibrator_bundle["method"]
    model = calibrator_bundle["model"]
    if method == "isotonic":
        return np.asarray(model.predict(raw_scores), dtype=float)
    if method == "platt":
        return np.asarray(model.predict_proba(raw_scores.reshape(-1, 1))[:, 1], dtype=float)
    raise ValueError(f"Unsupported calibration bundle method: {method}")


def render_metrics_table(rows: list[tuple[str, dict[str, float]]]) -> str:
    header = "| Model | Macro-F1 | Weighted-F1 | Log Loss | Brier | ECE |"
    divider = "| --- | ---: | ---: | ---: | ---: | ---: |"
    lines = [header, divider]
    for label, metrics in rows:
        lines.append(
            "| "
            f"{label} | "
            f"{metrics['macro_f1']:.4f} | "
            f"{metrics['weighted_f1']:.4f} | "
            f"{metrics['log_loss']:.4f} | "
            f"{metrics['brier']:.4f} | "
            f"{metrics['ece']:.4f} |"
        )
    return "\n".join(lines)


def build_training_report(
    *,
    output_run_dir: Path,
    feature_run_dir: Path,
    dataset_dir: Path,
    model_family: str,
    calibration_method: str,
    feature_count: int,
    split_sizes: dict[str, int],
    train_positive_rate: float,
    baseline_validation: dict[str, float],
    baseline_test: dict[str, float],
    primary_validation_raw: dict[str, float],
    primary_validation_calibrated: dict[str, float],
    primary_test_raw: dict[str, float],
    primary_test_calibrated: dict[str, float],
    best_params: dict[str, Any],
    search_ranked: list[SearchResult],
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    top_candidates = search_ranked[: min(5, len(search_ranked))]
    candidate_lines = []
    for rank, candidate in enumerate(top_candidates, start=1):
        candidate_lines.append(
            f"{rank}. `log_loss={candidate.mean_log_loss:.5f}`, "
            f"`macro_f1={candidate.mean_macro_f1:.5f}`, "
            f"`weighted_f1={candidate.mean_weighted_f1:.5f}`, "
            f"`brier={candidate.mean_brier:.5f}`, "
            f"`ece={candidate.mean_ece:.5f}` with params `{json.dumps(candidate.params, sort_keys=True)}`"
        )

    report = [
        "# Severity Training Report",
        "",
        "## Run Summary",
        f"- Generated at (UTC): `{generated_at}`",
        f"- Feature run directory: `{feature_run_dir}`",
        f"- Dataset directory: `{dataset_dir}`",
        f"- Output directory: `{output_run_dir}`",
        f"- Primary model family: `{model_family}`",
        f"- Calibration method: `{calibration_method}`",
        f"- Feature count: `{feature_count}`",
        f"- Split sizes: train={split_sizes['train']}, validation={split_sizes['validation']}, test={split_sizes['test']}",
        f"- Train positive class rate: `{train_positive_rate:.4f}`",
        "",
        "## Baseline (Regularized Logistic Regression)",
        render_metrics_table(
            [
                ("Baseline - Validation", baseline_validation),
                ("Baseline - Test", baseline_test),
            ]
        ),
        "",
        "## Primary Model Performance",
        render_metrics_table(
            [
                ("Primary Raw - Validation", primary_validation_raw),
                ("Primary Calibrated - Validation", primary_validation_calibrated),
                ("Primary Raw - Test", primary_test_raw),
                ("Primary Calibrated - Test", primary_test_calibrated),
            ]
        ),
        "",
        "## Hyperparameter Search (Time-Aware Validation)",
        f"- Best params: `{json.dumps(best_params, sort_keys=True)}`",
        f"- Candidates evaluated: `{len(search_ranked)}`",
        "- Top candidates:",
        *[f"  {line}" for line in candidate_lines],
        "",
        "## Exported Artifacts",
        "- `severity_model.pkl`",
        "- `severity_calibrator.pkl`",
        "- `severity_feature_list.json`",
        "- `severity_training_report.md`",
        "",
    ]
    return "\n".join(report)


def main() -> None:
    args = parse_args()
    feature_run_dir = resolve_feature_run_dir(
        feature_root=args.feature_root,
        version=args.snapshot_version,
        extraction_date=args.extraction_date,
    )
    resolved_extraction_date = feature_run_dir.name.split("=", maxsplit=1)[-1]
    dataset_dir = feature_run_dir / args.dataset_name
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    x_train, y_train, keys_train = load_split_dataset(dataset_dir, "train")
    x_val, y_val, _keys_val = load_split_dataset(dataset_dir, "validation")
    x_test, y_test, _keys_test = load_split_dataset(dataset_dir, "test")

    if x_train.empty or x_val.empty or x_test.empty:
        raise ValueError("One or more feature splits are empty.")
    if len(np.unique(y_train)) < 2:
        raise ValueError("Training split must include both classes for classification.")

    folds = build_time_aware_folds(
        keys_train=keys_train,
        y_train=y_train,
        n_splits=args.time_splits,
        min_train_fraction=args.min_train_fraction,
    )
    baseline_model = fit_baseline_model(
        x_train=x_train, y_train=y_train, c_value=args.logreg_c, seed=args.random_seed
    )

    baseline_val_prob = predicted_positive_proba(baseline_model, x_val)
    baseline_test_prob = predicted_positive_proba(baseline_model, x_test)
    baseline_validation_metrics = compute_binary_metrics(y_val, baseline_val_prob)
    baseline_test_metrics = compute_binary_metrics(y_test, baseline_test_prob)

    family = resolve_primary_family(args.model_family)
    best_params, ranked_search = search_primary_model(
        family=family,
        x_train=x_train,
        y_train=y_train,
        folds=folds,
        iterations=args.search_iterations,
        seed=args.random_seed,
        n_jobs=args.n_jobs,
    )
    class_ratio = positive_class_ratio(y_train)
    primary_model = build_primary_model(
        family=family,
        params=best_params,
        class_ratio=class_ratio,
        seed=args.random_seed,
        n_jobs=args.n_jobs,
    )
    primary_model.fit(x_train, y_train)

    primary_val_raw = predicted_positive_proba(primary_model, x_val)
    primary_test_raw = predicted_positive_proba(primary_model, x_test)
    primary_validation_raw_metrics = compute_binary_metrics(y_val, primary_val_raw)
    primary_test_raw_metrics = compute_binary_metrics(y_test, primary_test_raw)

    calibrator_bundle = fit_calibrator(
        method=args.calibration_method,
        raw_scores=primary_val_raw,
        y_true=y_val,
        seed=args.random_seed,
    )
    primary_val_calibrated = apply_calibrator(calibrator_bundle, primary_val_raw)
    primary_test_calibrated = apply_calibrator(calibrator_bundle, primary_test_raw)
    primary_validation_calibrated_metrics = compute_binary_metrics(y_val, primary_val_calibrated)
    primary_test_calibrated_metrics = compute_binary_metrics(y_test, primary_test_calibrated)

    output_run_dir = (
        args.output_root
        / f"version={args.snapshot_version}"
        / f"extraction_date={resolved_extraction_date}"
    )
    output_run_dir.mkdir(parents=True, exist_ok=True)

    feature_list_path = output_run_dir / "severity_feature_list.json"
    model_path = output_run_dir / "severity_model.pkl"
    calibrator_path = output_run_dir / "severity_calibrator.pkl"
    report_path = output_run_dir / "severity_training_report.md"

    with feature_list_path.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "feature_count": int(x_train.shape[1]),
                "features": list(x_train.columns),
            },
            file,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )

    with model_path.open("wb") as file:
        pickle.dump(
            {
                "model_family": family,
                "best_params": best_params,
                "feature_names": list(x_train.columns),
                "model": primary_model,
                "baseline_model": baseline_model,
                "trained_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            file,
            protocol=pickle.HIGHEST_PROTOCOL,
        )
    with calibrator_path.open("wb") as file:
        pickle.dump(calibrator_bundle, file, protocol=pickle.HIGHEST_PROTOCOL)

    report_text = build_training_report(
        output_run_dir=output_run_dir,
        feature_run_dir=feature_run_dir,
        dataset_dir=dataset_dir,
        model_family=family,
        calibration_method=args.calibration_method,
        feature_count=int(x_train.shape[1]),
        split_sizes={
            "train": int(len(x_train)),
            "validation": int(len(x_val)),
            "test": int(len(x_test)),
        },
        train_positive_rate=float(np.mean(y_train)),
        baseline_validation=baseline_validation_metrics,
        baseline_test=baseline_test_metrics,
        primary_validation_raw=primary_validation_raw_metrics,
        primary_validation_calibrated=primary_validation_calibrated_metrics,
        primary_test_raw=primary_test_raw_metrics,
        primary_test_calibrated=primary_test_calibrated_metrics,
        best_params=best_params,
        search_ranked=ranked_search,
    )
    with report_path.open("w", encoding="utf-8") as file:
        file.write(report_text)

    summary = {
        "feature_run_dir": str(feature_run_dir),
        "dataset_dir": str(dataset_dir),
        "output_run_dir": str(output_run_dir),
        "model_family": family,
        "calibration_method": args.calibration_method,
        "best_params": best_params,
        "baseline_validation_metrics": baseline_validation_metrics,
        "baseline_test_metrics": baseline_test_metrics,
        "primary_validation_raw_metrics": primary_validation_raw_metrics,
        "primary_validation_calibrated_metrics": primary_validation_calibrated_metrics,
        "primary_test_raw_metrics": primary_test_raw_metrics,
        "primary_test_calibrated_metrics": primary_test_calibrated_metrics,
        "artifacts": {
            "severity_model_pkl": str(model_path),
            "severity_calibrator_pkl": str(calibrator_path),
            "severity_feature_list_json": str(feature_list_path),
            "severity_training_report_md": str(report_path),
        },
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
