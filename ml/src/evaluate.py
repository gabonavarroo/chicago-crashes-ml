"""Offline evaluation entry point for severity and hotspot models."""

from __future__ import annotations

import argparse
import json
import math
import pickle
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    mean_absolute_error,
    mean_poisson_deviance,
    mean_squared_error,
)

EPSILON = 1e-9


@dataclass(frozen=True)
class GateThresholds:
    min_severity_pr_auc: float
    min_severity_recall_top_k_percentile: float
    max_severity_brier: float
    max_hotspot_mae: float
    max_hotspot_rmse: float
    max_hotspot_poisson_deviance: float
    min_hotspot_top_k_hit_rate: float
    min_combined_precision: float
    min_combined_recall: float
    min_combined_join_coverage: float
    max_severity_slice_drop: float
    max_hotspot_slice_rmse_ratio: float


def parse_args() -> argparse.Namespace:
    root_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Evaluate severity and hotspot models and run release-gate checks."
    )
    parser.add_argument(
        "--feature-root",
        type=Path,
        default=root_dir / "artifacts" / "features",
        help="Feature artifact base directory.",
    )
    parser.add_argument(
        "--severity-model-root",
        type=Path,
        default=root_dir / "artifacts" / "models" / "severity",
        help="Severity model artifact base directory.",
    )
    parser.add_argument(
        "--hotspot-model-root",
        type=Path,
        default=root_dir / "artifacts" / "models" / "hotspot",
        help="Hotspot model artifact base directory.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=root_dir / "artifacts" / "evaluation",
        help="Evaluation output base directory.",
    )
    parser.add_argument(
        "--snapshot-version",
        type=str,
        default="v1",
        help="Feature/model version namespace.",
    )
    parser.add_argument(
        "--extraction-date",
        type=str,
        default=None,
        help="Extraction date (YYYY-MM-DD). If omitted, latest available in feature-root is used.",
    )
    parser.add_argument(
        "--split",
        choices=["validation", "test"],
        default="test",
        help="Split used for evaluation.",
    )
    parser.add_argument(
        "--severity-top-k-percentile",
        type=float,
        default=95.0,
        help="Percentile defining top-risk bucket for severity recall@top-k-percentile.",
    )
    parser.add_argument(
        "--reliability-bins",
        type=int,
        default=10,
        help="Number of bins for reliability diagnostics.",
    )
    parser.add_argument(
        "--hotspot-top-k-zones",
        type=int,
        default=1000,
        help="Top-K zones for hotspot hit-rate metric.",
    )
    parser.add_argument(
        "--combined-top-k-zones",
        type=int,
        default=1000,
        help="Top-K zones for combined expected_severe_harm precision/recall.",
    )
    parser.add_argument(
        "--min-severity-slice-rows",
        type=int,
        default=2000,
        help="Minimum rows per severity slice for stability checks.",
    )
    parser.add_argument(
        "--min-hotspot-slice-rows",
        type=int,
        default=500,
        help="Minimum rows per hotspot slice for stability checks.",
    )

    # Release-gate thresholds.
    parser.add_argument("--gate-min-severity-pr-auc", type=float, default=0.10)
    parser.add_argument(
        "--gate-min-severity-recall-top-k-percentile",
        type=float,
        default=0.25,
    )
    parser.add_argument("--gate-max-severity-brier", type=float, default=0.03)
    parser.add_argument("--gate-max-hotspot-mae", type=float, default=0.15)
    parser.add_argument("--gate-max-hotspot-rmse", type=float, default=0.30)
    parser.add_argument("--gate-max-hotspot-poisson-deviance", type=float, default=0.10)
    parser.add_argument("--gate-min-hotspot-top-k-hit-rate", type=float, default=0.01)
    parser.add_argument("--gate-min-combined-precision", type=float, default=0.10)
    parser.add_argument("--gate-min-combined-recall", type=float, default=0.08)
    parser.add_argument("--gate-min-combined-join-coverage", type=float, default=0.95)
    parser.add_argument("--gate-max-severity-slice-drop", type=float, default=0.08)
    parser.add_argument("--gate-max-hotspot-slice-rmse-ratio", type=float, default=1.75)
    return parser.parse_args()


def resolve_run_dir(base_root: Path, version: str, extraction_date: str | None) -> Path:
    version_dir = base_root / f"version={version}"
    if not version_dir.exists():
        raise FileNotFoundError(f"Version directory not found: {version_dir}")
    if extraction_date:
        selected = version_dir / f"extraction_date={extraction_date}"
        if not selected.exists():
            raise FileNotFoundError(f"Extraction directory not found: {selected}")
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
    y = pd.to_numeric(y_frame.iloc[:, 0], errors="coerce").to_numpy(dtype=float)
    if np.isnan(y).any():
        bad = int(np.isnan(y).sum())
        raise ValueError(f"Target contains {bad} non-numeric rows in split '{split_name}'.")
    return x_frame, y, keys_frame


def load_pickle(path: Path) -> Any:
    with path.open("rb") as file:
        return pickle.load(file)


def clip_probs(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = np.where(np.isfinite(arr), arr, 0.5)
    return np.clip(arr, EPSILON, 1.0 - EPSILON)


def clip_counts(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = np.where(np.isfinite(arr), arr, np.nan)
    finite = arr[np.isfinite(arr)]
    fallback = float(np.mean(finite)) if len(finite) else 1.0
    arr = np.where(np.isfinite(arr), arr, fallback)
    return np.clip(arr, EPSILON, None)


def top_k_indices(scores: np.ndarray, k: int) -> np.ndarray:
    if k <= 0:
        raise ValueError("k must be positive.")
    values = np.asarray(scores, dtype=float)
    if len(values) == 0:
        return np.array([], dtype=int)
    k = min(k, len(values))
    order = np.argsort(-values, kind="mergesort")
    return order[:k]


def percentile_to_k(size: int, percentile: float) -> int:
    clipped = min(max(percentile, 0.0), 100.0)
    tail_fraction = max((100.0 - clipped) / 100.0, 1.0 / max(size, 1))
    return max(1, int(math.ceil(size * tail_fraction)))


def apply_severity_calibrator(calibrator_bundle: dict[str, Any], raw_scores: np.ndarray) -> np.ndarray:
    method = calibrator_bundle["method"]
    model = calibrator_bundle["model"]
    if method == "isotonic":
        probs = model.predict(raw_scores)
    elif method == "platt":
        probs = model.predict_proba(raw_scores.reshape(-1, 1))[:, 1]
    else:
        raise ValueError(f"Unsupported calibration method: {method}")
    return clip_probs(np.asarray(probs, dtype=float))


def reliability_bins(y_true: np.ndarray, y_prob: np.ndarray, bins: int) -> list[dict[str, float]]:
    if bins < 2:
        raise ValueError("--reliability-bins must be >= 2.")
    truth = np.asarray(y_true, dtype=float)
    probs = clip_probs(y_prob)
    boundaries = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, float]] = []
    for idx in range(bins):
        left = boundaries[idx]
        right = boundaries[idx + 1]
        if idx == bins - 1:
            mask = (probs >= left) & (probs <= right)
        else:
            mask = (probs >= left) & (probs < right)
        count = int(mask.sum())
        if count == 0:
            rows.append(
                {
                    "bin_start": float(left),
                    "bin_end": float(right),
                    "count": 0,
                    "predicted_mean": 0.0,
                    "observed_rate": 0.0,
                    "abs_gap": 0.0,
                }
            )
            continue
        predicted_mean = float(np.mean(probs[mask]))
        observed_rate = float(np.mean(truth[mask]))
        rows.append(
            {
                "bin_start": float(left),
                "bin_end": float(right),
                "count": count,
                "predicted_mean": predicted_mean,
                "observed_rate": observed_rate,
                "abs_gap": float(abs(observed_rate - predicted_mean)),
            }
        )
    return rows


def season_from_timestamp(ts: pd.Series) -> pd.Series:
    month = ts.dt.month
    season = pd.Series(index=ts.index, dtype="object")
    season[(month == 12) | (month <= 2)] = "winter"
    season[(month >= 3) & (month <= 5)] = "spring"
    season[(month >= 6) & (month <= 8)] = "summer"
    season[(month >= 9) & (month <= 11)] = "fall"
    return season.fillna("unknown")


def weekpart_from_timestamp(ts: pd.Series) -> pd.Series:
    weekday_idx = ts.dt.weekday
    return pd.Series(np.where(weekday_idx >= 5, "weekend", "weekday"), index=ts.index)


def geography_bin_from_lat_lon(lat: np.ndarray, lon: np.ndarray, degrees: float = 0.10) -> pd.Series:
    lat_arr = np.asarray(lat, dtype=float)
    lon_arr = np.asarray(lon, dtype=float)
    labels = np.full(len(lat_arr), "unknown", dtype=object)
    valid = np.isfinite(lat_arr) & np.isfinite(lon_arr)
    if not np.any(valid):
        return pd.Series(labels)
    lat_bins = np.floor(lat_arr[valid] / degrees).astype(int)
    lon_bins = np.floor(lon_arr[valid] / degrees).astype(int)
    labels[valid] = [f"lat{a}_lon{b}" for a, b in zip(lat_bins, lon_bins)]
    return pd.Series(labels)


GRID_REGEX = re.compile(r"^lat(?P<lat>-?\d+)_lon(?P<lon>-?\d+)$")


def geography_bin_from_grid_id(grid_id: pd.Series) -> pd.Series:
    bins: list[str] = []
    for value in grid_id.astype(str):
        match = GRID_REGEX.match(value)
        if not match:
            bins.append("unknown")
            continue
        lat_bin = int(match.group("lat"))
        lon_bin = int(match.group("lon"))
        bins.append(f"lat{lat_bin // 10}_lon{math.floor(lon_bin / 10)}")
    return pd.Series(bins, index=grid_id.index)


def safe_correlation(x: np.ndarray, y: np.ndarray) -> float:
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    valid = np.isfinite(x_arr) & np.isfinite(y_arr)
    if valid.sum() < 3:
        return 0.0
    x_use = x_arr[valid]
    y_use = y_arr[valid]
    if np.allclose(np.std(x_use), 0.0) or np.allclose(np.std(y_use), 0.0):
        return 0.0
    return float(np.corrcoef(x_use, y_use)[0, 1])


def compute_severity_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    top_k_percentile: float,
    bins: int,
) -> dict[str, Any]:
    truth = (np.asarray(y_true, dtype=float) > 0).astype(int)
    probs = clip_probs(y_prob)
    k = percentile_to_k(len(probs), top_k_percentile)
    top_idx = top_k_indices(probs, k)
    positives = int(truth.sum())
    top_true_positives = int(truth[top_idx].sum())
    recall_top = float(top_true_positives / max(positives, 1))
    return {
        "primary_metric": "pr_auc",
        "pr_auc": float(average_precision_score(truth, probs)),
        "recall_at_top_k_percentile": {
            "percentile": float(top_k_percentile),
            "k": int(k),
            "recall": recall_top,
            "precision_in_top_k": float(top_true_positives / max(k, 1)),
            "true_positives_in_top_k": top_true_positives,
            "total_positives": positives,
        },
        "calibration": {
            "brier_score": float(brier_score_loss(truth, probs)),
            "reliability_bins": reliability_bins(truth, probs, bins=bins),
        },
    }


def compute_hotspot_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    top_k_zones: int,
    include_poisson: bool,
) -> dict[str, Any]:
    truth = np.clip(np.asarray(y_true, dtype=float), 0.0, None)
    pred = clip_counts(y_pred)
    rmse = float(np.sqrt(mean_squared_error(truth, pred)))
    mae = float(mean_absolute_error(truth, pred))
    k = max(1, min(top_k_zones, len(pred)))
    pred_top = set(top_k_indices(pred, k).tolist())
    true_top = set(top_k_indices(truth, k).tolist())
    hit_rate = float(len(pred_top.intersection(true_top)) / max(k, 1))

    poisson_deviance: float | None = None
    if include_poisson:
        poisson_deviance = float(mean_poisson_deviance(truth, pred))
    return {
        "mae": mae,
        "rmse": rmse,
        "poisson_deviance": poisson_deviance,
        "top_k_hotspot_hit_rate": {
            "k": int(k),
            "hit_rate": hit_rate,
            "hits": int(len(pred_top.intersection(true_top))),
        },
    }


def derive_grid_id_from_coordinates(latitude: np.ndarray, longitude: np.ndarray) -> pd.Series:
    lat_arr = np.asarray(latitude, dtype=float)
    lon_arr = np.asarray(longitude, dtype=float)
    values: list[str] = []
    for lat, lon in zip(lat_arr, lon_arr):
        if np.isfinite(lat) and np.isfinite(lon):
            lat_bin = int(math.floor(lat / 0.01))
            lon_bin = int(math.floor(lon / 0.01))
            values.append(f"lat{lat_bin}_lon{lon_bin}")
        else:
            values.append("lat0_lon0")
    return pd.Series(values)


def build_combined_frame(
    severity_keys: pd.DataFrame,
    severity_x: pd.DataFrame,
    severity_y_true: np.ndarray,
    severity_y_prob: np.ndarray,
    hotspot_keys: pd.DataFrame,
    hotspot_y_true: np.ndarray,
    hotspot_y_pred: np.ndarray,
) -> tuple[pd.DataFrame, float]:
    severity_time = pd.to_datetime(severity_keys.iloc[:, -1], errors="coerce").dt.floor("h")
    if severity_time.isna().any():
        bad = int(severity_time.isna().sum())
        raise ValueError(f"Severity key time column contains {bad} unparsable timestamps.")
    severity_grid = derive_grid_id_from_coordinates(
        latitude=severity_x["latitude"].to_numpy(dtype=float),
        longitude=severity_x["longitude"].to_numpy(dtype=float),
    )
    severity_rows = pd.DataFrame(
        {
            "grid_id": severity_grid,
            "time_bucket": severity_time,
            "severity_prob": clip_probs(severity_y_prob),
            "actual_severe": (np.asarray(severity_y_true, dtype=float) > 0).astype(int),
        }
    )
    severity_agg = severity_rows.groupby(["grid_id", "time_bucket"], as_index=False).agg(
        severity_prob=("severity_prob", "mean"),
        actual_severe_count=("actual_severe", "sum"),
        crash_events=("actual_severe", "size"),
    )

    hotspot_time = pd.to_datetime(hotspot_keys.iloc[:, -1], errors="coerce").dt.floor("h")
    if hotspot_time.isna().any():
        bad = int(hotspot_time.isna().sum())
        raise ValueError(f"Hotspot key time column contains {bad} unparsable timestamps.")
    hotspot_rows = pd.DataFrame(
        {
            "grid_id": hotspot_keys.iloc[:, 0].astype(str).to_numpy(),
            "time_bucket": hotspot_time.to_numpy(),
            "predicted_count": clip_counts(hotspot_y_pred),
            "actual_count": np.clip(np.asarray(hotspot_y_true, dtype=float), 0.0, None),
        }
    )
    merged = hotspot_rows.merge(
        severity_agg,
        on=["grid_id", "time_bucket"],
        how="left",
        indicator=True,
    )
    matched_ratio = float((merged["_merge"] == "both").mean())
    merged.drop(columns=["_merge"], inplace=True)
    baseline_rate = float(np.mean((np.asarray(severity_y_true, dtype=float) > 0).astype(float)))
    merged["severity_prob"] = merged["severity_prob"].fillna(baseline_rate)
    merged["actual_severe_count"] = merged["actual_severe_count"].fillna(0.0)
    merged["crash_events"] = merged["crash_events"].fillna(0).astype(int)
    merged["expected_severe_harm"] = merged["predicted_count"] * merged["severity_prob"]
    return merged, matched_ratio


def compute_combined_metrics(combined: pd.DataFrame, top_k_zones: int) -> dict[str, Any]:
    expected = combined["expected_severe_harm"].to_numpy(dtype=float)
    actual_severe_count = combined["actual_severe_count"].to_numpy(dtype=float)
    actual_positive = actual_severe_count > 0

    k = max(1, min(top_k_zones, len(combined)))
    pred_top_idx = top_k_indices(expected, k)
    true_positive_hits = int(np.sum(actual_positive[pred_top_idx]))
    precision = float(true_positive_hits / max(k, 1))
    recall = float(true_positive_hits / max(int(actual_positive.sum()), 1))

    return {
        "precision_recall_on_top_expected_severe_harm_zones": {
            "k": int(k),
            "precision": precision,
            "recall": recall,
            "true_positive_zones": true_positive_hits,
            "total_actual_positive_zones": int(actual_positive.sum()),
        },
        "expected_severe_harm_summary": {
            "max": float(np.max(expected)) if len(expected) else 0.0,
            "mean": float(np.mean(expected)) if len(expected) else 0.0,
            "p95": float(np.quantile(expected, 0.95)) if len(expected) else 0.0,
        },
    }


def severity_slice_metrics(
    frame: pd.DataFrame,
    top_k_percentile: float,
    min_rows: int,
) -> dict[str, dict[str, dict[str, float]]]:
    result: dict[str, dict[str, dict[str, float]]] = {}
    for dimension in ("season", "week_part", "geography"):
        rows: dict[str, dict[str, float]] = {}
        for key, group in frame.groupby(dimension):
            if len(group) < min_rows:
                continue
            truth = group["y_true"].to_numpy(dtype=int)
            probs = group["y_prob"].to_numpy(dtype=float)
            if int(truth.sum()) < 5:
                continue
            k = percentile_to_k(len(group), top_k_percentile)
            top_idx = top_k_indices(probs, k)
            rows[str(key)] = {
                "rows": float(len(group)),
                "positive_rate": float(np.mean(truth)),
                "pr_auc": float(average_precision_score(truth, probs)),
                "recall_at_top_k_percentile": float(np.sum(truth[top_idx]) / max(int(truth.sum()), 1)),
                "brier_score": float(brier_score_loss(truth, clip_probs(probs))),
            }
        result[dimension] = rows
    return result


def hotspot_slice_metrics(frame: pd.DataFrame, min_rows: int) -> dict[str, dict[str, dict[str, float]]]:
    result: dict[str, dict[str, dict[str, float]]] = {}
    for dimension in ("season", "week_part", "geography"):
        rows: dict[str, dict[str, float]] = {}
        for key, group in frame.groupby(dimension):
            if len(group) < min_rows:
                continue
            truth = group["y_true"].to_numpy(dtype=float)
            pred = group["y_pred"].to_numpy(dtype=float)
            rows[str(key)] = {
                "rows": float(len(group)),
                "mean_true_count": float(np.mean(truth)),
                "mae": float(mean_absolute_error(truth, pred)),
                "rmse": float(np.sqrt(mean_squared_error(truth, pred))),
            }
        result[dimension] = rows
    return result


def evaluate_stability(
    severity_overall_pr_auc: float,
    hotspot_overall_rmse: float,
    severity_slices: dict[str, dict[str, dict[str, float]]],
    hotspot_slices: dict[str, dict[str, dict[str, float]]],
    thresholds: GateThresholds,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for dimension in ("season", "week_part", "geography"):
        sev_dimension = severity_slices.get(dimension, {})
        sev_values = [row["pr_auc"] for row in sev_dimension.values()]
        if sev_values:
            worst = float(min(sev_values))
            drop = float(severity_overall_pr_auc - worst)
            passed = drop <= thresholds.max_severity_slice_drop
            checks.append(
                {
                    "name": f"severity_stability_{dimension}",
                    "pass": bool(passed),
                    "worst_slice_value": worst,
                    "overall_value": severity_overall_pr_auc,
                    "drop": drop,
                    "max_allowed_drop": thresholds.max_severity_slice_drop,
                    "eligible_slices": int(len(sev_values)),
                }
            )
        else:
            checks.append(
                {
                    "name": f"severity_stability_{dimension}",
                    "pass": False,
                    "reason": "no_eligible_slices",
                }
            )

        hot_dimension = hotspot_slices.get(dimension, {})
        hot_values = [row["rmse"] for row in hot_dimension.values()]
        if hot_values:
            worst_rmse = float(max(hot_values))
            ratio = float(worst_rmse / max(hotspot_overall_rmse, EPSILON))
            passed = ratio <= thresholds.max_hotspot_slice_rmse_ratio
            checks.append(
                {
                    "name": f"hotspot_stability_{dimension}",
                    "pass": bool(passed),
                    "worst_slice_value": worst_rmse,
                    "overall_value": hotspot_overall_rmse,
                    "rmse_ratio": ratio,
                    "max_allowed_rmse_ratio": thresholds.max_hotspot_slice_rmse_ratio,
                    "eligible_slices": int(len(hot_values)),
                }
            )
        else:
            checks.append(
                {
                    "name": f"hotspot_stability_{dimension}",
                    "pass": False,
                    "reason": "no_eligible_slices",
                }
            )
    return {
        "checks": checks,
        "pass": bool(all(item["pass"] for item in checks)),
    }


def run_bias_sanity_checks(
    *,
    severity_features: list[str],
    severity_prob: np.ndarray,
    severity_x: pd.DataFrame,
    hotspot_features: list[str],
    hotspot_pred: np.ndarray,
    combined_join_coverage: float,
    min_join_coverage: float,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    lowered_severity = [name.lower() for name in severity_features]
    id_like_patterns = ("record_id", "case_number", "collision_id")
    severity_has_id_like = any(any(pattern in name for pattern in id_like_patterns) for name in lowered_severity)
    checks.append(
        {
            "name": "severity_no_id_like_features",
            "pass": not severity_has_id_like,
            "detail": "Feature list must not contain obvious identifier columns.",
        }
    )

    severity_has_target_leak = any("severe_injury_flag" in name for name in lowered_severity)
    checks.append(
        {
            "name": "severity_no_target_leak_feature",
            "pass": not severity_has_target_leak,
            "detail": "Feature list must not contain target columns.",
        }
    )

    severity_std = float(np.std(severity_prob))
    checks.append(
        {
            "name": "severity_prediction_not_constant",
            "pass": bool(severity_std >= 1e-4),
            "value": severity_std,
            "min_required": 1e-4,
        }
    )

    lat_corr = safe_correlation(severity_prob, severity_x["latitude"].to_numpy(dtype=float))
    lon_corr = safe_correlation(severity_prob, severity_x["longitude"].to_numpy(dtype=float))
    coord_corr_abs_max = float(max(abs(lat_corr), abs(lon_corr)))
    checks.append(
        {
            "name": "severity_prediction_not_geo_artifact",
            "pass": bool(coord_corr_abs_max < 0.98),
            "value": coord_corr_abs_max,
            "max_allowed": 0.98,
            "latitude_corr": float(lat_corr),
            "longitude_corr": float(lon_corr),
        }
    )

    lowered_hotspot = [name.lower() for name in hotspot_features]
    hotspot_has_target_leak = any("crash_count" in name for name in lowered_hotspot)
    checks.append(
        {
            "name": "hotspot_no_target_leak_feature",
            "pass": not hotspot_has_target_leak,
            "detail": "Feature list must not contain target columns.",
        }
    )

    finite_positive = bool(np.isfinite(hotspot_pred).all() and (hotspot_pred > 0).all())
    checks.append(
        {
            "name": "hotspot_prediction_finite_positive",
            "pass": finite_positive,
        }
    )

    hotspot_std = float(np.std(hotspot_pred))
    checks.append(
        {
            "name": "hotspot_prediction_not_constant",
            "pass": bool(hotspot_std >= 1e-4),
            "value": hotspot_std,
            "min_required": 1e-4,
        }
    )

    one_percent_k = max(1, int(math.ceil(len(hotspot_pred) * 0.01)))
    top_idx = top_k_indices(hotspot_pred, one_percent_k)
    concentration = float(np.sum(hotspot_pred[top_idx]) / max(float(np.sum(hotspot_pred)), EPSILON))
    checks.append(
        {
            "name": "hotspot_top_1pct_concentration",
            "pass": bool(concentration <= 0.75),
            "value": concentration,
            "max_allowed": 0.75,
        }
    )

    checks.append(
        {
            "name": "combined_join_coverage",
            "pass": bool(combined_join_coverage >= min_join_coverage),
            "value": combined_join_coverage,
            "min_required": min_join_coverage,
        }
    )

    return {
        "checks": checks,
        "pass": bool(all(item["pass"] for item in checks)),
    }


def release_gate_rows(
    severity_metrics: dict[str, Any],
    hotspot_metrics: dict[str, Any],
    combined_metrics: dict[str, Any],
    stability: dict[str, Any],
    sanity: dict[str, Any],
    thresholds: GateThresholds,
    poisson_required: bool,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    recall_top = severity_metrics["recall_at_top_k_percentile"]["recall"]
    brier = severity_metrics["calibration"]["brier_score"]
    rows.extend(
        [
            {
                "name": "severity_pr_auc_minimum",
                "pass": severity_metrics["pr_auc"] >= thresholds.min_severity_pr_auc,
                "value": severity_metrics["pr_auc"],
                "threshold": thresholds.min_severity_pr_auc,
                "direction": ">=",
            },
            {
                "name": "severity_recall_at_top_k_percentile_minimum",
                "pass": recall_top >= thresholds.min_severity_recall_top_k_percentile,
                "value": recall_top,
                "threshold": thresholds.min_severity_recall_top_k_percentile,
                "direction": ">=",
            },
            {
                "name": "severity_brier_maximum",
                "pass": brier <= thresholds.max_severity_brier,
                "value": brier,
                "threshold": thresholds.max_severity_brier,
                "direction": "<=",
            },
        ]
    )

    rows.extend(
        [
            {
                "name": "hotspot_mae_maximum",
                "pass": hotspot_metrics["mae"] <= thresholds.max_hotspot_mae,
                "value": hotspot_metrics["mae"],
                "threshold": thresholds.max_hotspot_mae,
                "direction": "<=",
            },
            {
                "name": "hotspot_rmse_maximum",
                "pass": hotspot_metrics["rmse"] <= thresholds.max_hotspot_rmse,
                "value": hotspot_metrics["rmse"],
                "threshold": thresholds.max_hotspot_rmse,
                "direction": "<=",
            },
            {
                "name": "hotspot_top_k_hit_rate_minimum",
                "pass": hotspot_metrics["top_k_hotspot_hit_rate"]["hit_rate"]
                >= thresholds.min_hotspot_top_k_hit_rate,
                "value": hotspot_metrics["top_k_hotspot_hit_rate"]["hit_rate"],
                "threshold": thresholds.min_hotspot_top_k_hit_rate,
                "direction": ">=",
            },
        ]
    )

    if poisson_required:
        rows.append(
            {
                "name": "hotspot_poisson_deviance_maximum",
                "pass": hotspot_metrics["poisson_deviance"] <= thresholds.max_hotspot_poisson_deviance,
                "value": hotspot_metrics["poisson_deviance"],
                "threshold": thresholds.max_hotspot_poisson_deviance,
                "direction": "<=",
            }
        )
    else:
        rows.append(
            {
                "name": "hotspot_poisson_deviance_maximum",
                "pass": True,
                "status": "skipped",
                "reason": "poisson_deviance_not_required_for_selected_objective",
            }
        )

    combined_pr = combined_metrics["precision_recall_on_top_expected_severe_harm_zones"]["precision"]
    combined_rc = combined_metrics["precision_recall_on_top_expected_severe_harm_zones"]["recall"]
    rows.extend(
        [
            {
                "name": "combined_precision_minimum",
                "pass": combined_pr >= thresholds.min_combined_precision,
                "value": combined_pr,
                "threshold": thresholds.min_combined_precision,
                "direction": ">=",
            },
            {
                "name": "combined_recall_minimum",
                "pass": combined_rc >= thresholds.min_combined_recall,
                "value": combined_rc,
                "threshold": thresholds.min_combined_recall,
                "direction": ">=",
            },
        ]
    )

    rows.append(
        {
            "name": "stability_checks",
            "pass": bool(stability["pass"]),
            "detail": "season, weekday/weekend, geography",
        }
    )
    rows.append(
        {
            "name": "bias_sanity_checks",
            "pass": bool(sanity["pass"]),
            "detail": "artifact and leakage sanity checks",
        }
    )
    return {
        "checks": rows,
        "pass": bool(all(item["pass"] for item in rows)),
    }


def to_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): to_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [to_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def build_markdown_report(
    *,
    split: str,
    run_date: str,
    severity_metrics: dict[str, Any],
    hotspot_metrics: dict[str, Any],
    combined_metrics: dict[str, Any],
    release_gates: dict[str, Any],
    stability: dict[str, Any],
    sanity: dict[str, Any],
) -> str:
    status = "PASS" if release_gates["pass"] else "FAIL"
    lines = [
        "# Evaluation Report",
        "",
        "## Run Summary",
        f"- Generated at (UTC): `{datetime.now(timezone.utc).isoformat()}`",
        f"- Extraction date: `{run_date}`",
        f"- Split: `{split}`",
        f"- Release decision: `{status}`",
        "",
        "## Severity Metrics",
        f"- Primary metric `PR-AUC`: `{severity_metrics['pr_auc']:.6f}`",
        (
            "- Recall@Top-K risk percentile "
            f"(`p{severity_metrics['recall_at_top_k_percentile']['percentile']:.1f}`, "
            f"`k={severity_metrics['recall_at_top_k_percentile']['k']}`): "
            f"`{severity_metrics['recall_at_top_k_percentile']['recall']:.6f}`"
        ),
        f"- Brier score: `{severity_metrics['calibration']['brier_score']:.6f}`",
        "",
        "## Hotspot Metrics",
        f"- MAE on counts: `{hotspot_metrics['mae']:.6f}`",
        f"- RMSE on counts: `{hotspot_metrics['rmse']:.6f}`",
        (
            "- Poisson deviance: "
            f"`{hotspot_metrics['poisson_deviance']:.6f}`"
            if hotspot_metrics["poisson_deviance"] is not None
            else "- Poisson deviance: `skipped`"
        ),
        (
            "- Top-K hotspot hit rate "
            f"(`k={hotspot_metrics['top_k_hotspot_hit_rate']['k']}`): "
            f"`{hotspot_metrics['top_k_hotspot_hit_rate']['hit_rate']:.6f}`"
        ),
        "",
        "## Combined Operational Metric",
        (
            "- Precision on top-ranked `expected_severe_harm` zones "
            f"(`k={combined_metrics['precision_recall_on_top_expected_severe_harm_zones']['k']}`): "
            f"`{combined_metrics['precision_recall_on_top_expected_severe_harm_zones']['precision']:.6f}`"
        ),
        (
            "- Recall on top-ranked `expected_severe_harm` zones: "
            f"`{combined_metrics['precision_recall_on_top_expected_severe_harm_zones']['recall']:.6f}`"
        ),
        "",
        "## Release Gate Checks",
    ]
    for check in release_gates["checks"]:
        mark = "PASS" if check["pass"] else "FAIL"
        lines.append(f"- `{check['name']}`: `{mark}`")
    lines.extend(
        [
            "",
            "## Stability Checks",
            f"- Overall stability pass: `{'PASS' if stability['pass'] else 'FAIL'}`",
        ]
    )
    for check in stability["checks"]:
        mark = "PASS" if check["pass"] else "FAIL"
        lines.append(f"- `{check['name']}`: `{mark}`")
    lines.extend(
        [
            "",
            "## Bias/Sanity Checks",
            f"- Overall sanity pass: `{'PASS' if sanity['pass'] else 'FAIL'}`",
        ]
    )
    for check in sanity["checks"]:
        mark = "PASS" if check["pass"] else "FAIL"
        lines.append(f"- `{check['name']}`: `{mark}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    feature_run_dir = resolve_run_dir(
        base_root=args.feature_root,
        version=args.snapshot_version,
        extraction_date=args.extraction_date,
    )
    resolved_extraction_date = feature_run_dir.name.split("=", maxsplit=1)[-1]
    severity_model_run_dir = resolve_run_dir(
        base_root=args.severity_model_root,
        version=args.snapshot_version,
        extraction_date=resolved_extraction_date,
    )
    hotspot_model_run_dir = resolve_run_dir(
        base_root=args.hotspot_model_root,
        version=args.snapshot_version,
        extraction_date=resolved_extraction_date,
    )

    severity_dataset_dir = feature_run_dir / "severity"
    hotspot_dataset_dir = feature_run_dir / "hotspot"
    severity_x, severity_y, severity_keys = load_split_dataset(severity_dataset_dir, args.split)
    hotspot_x, hotspot_y, hotspot_keys = load_split_dataset(hotspot_dataset_dir, args.split)
    severity_y_binary = (severity_y > 0).astype(int)
    hotspot_y_nonneg = np.clip(hotspot_y, 0.0, None)

    severity_bundle = load_pickle(severity_model_run_dir / "severity_model.pkl")
    calibrator_bundle = load_pickle(severity_model_run_dir / "severity_calibrator.pkl")
    hotspot_bundle = load_pickle(hotspot_model_run_dir / "hotspot_model.pkl")

    severity_feature_names = list(severity_bundle.get("feature_names", list(severity_x.columns)))
    hotspot_feature_names = list(hotspot_bundle.get("feature_names", list(hotspot_x.columns)))
    severity_aligned = severity_x.reindex(columns=severity_feature_names, fill_value=0)
    hotspot_aligned = hotspot_x.reindex(columns=hotspot_feature_names, fill_value=0)

    raw_prob = np.asarray(severity_bundle["model"].predict_proba(severity_aligned)[:, 1], dtype=float)
    severity_prob = apply_severity_calibrator(calibrator_bundle, raw_prob)
    hotspot_pred = clip_counts(np.asarray(hotspot_bundle["primary_model"].predict(hotspot_aligned), dtype=float))

    severity_metrics = compute_severity_metrics(
        y_true=severity_y_binary,
        y_prob=severity_prob,
        top_k_percentile=args.severity_top_k_percentile,
        bins=args.reliability_bins,
    )

    resolved_family = str(hotspot_bundle.get("resolved_primary_family", "")).lower()
    requested_objective = str(hotspot_bundle.get("requested_objective", "")).lower()
    poisson_required = any(token in (resolved_family + "|" + requested_objective) for token in ("poisson", "tweedie"))
    hotspot_metrics = compute_hotspot_metrics(
        y_true=hotspot_y_nonneg,
        y_pred=hotspot_pred,
        top_k_zones=args.hotspot_top_k_zones,
        include_poisson=poisson_required,
    )

    combined_frame, combined_join_coverage = build_combined_frame(
        severity_keys=severity_keys,
        severity_x=severity_aligned,
        severity_y_true=severity_y_binary,
        severity_y_prob=severity_prob,
        hotspot_keys=hotspot_keys,
        hotspot_y_true=hotspot_y_nonneg,
        hotspot_y_pred=hotspot_pred,
    )
    combined_metrics = compute_combined_metrics(
        combined=combined_frame,
        top_k_zones=args.combined_top_k_zones,
    )

    severity_time = pd.to_datetime(severity_keys.iloc[:, -1], errors="coerce")
    severity_eval_frame = pd.DataFrame(
        {
            "y_true": severity_y_binary,
            "y_prob": severity_prob,
            "season": season_from_timestamp(severity_time),
            "week_part": weekpart_from_timestamp(severity_time),
            "geography": geography_bin_from_lat_lon(
                severity_aligned["latitude"].to_numpy(dtype=float),
                severity_aligned["longitude"].to_numpy(dtype=float),
            ),
        }
    )
    hotspot_time = pd.to_datetime(hotspot_keys.iloc[:, -1], errors="coerce")
    hotspot_eval_frame = pd.DataFrame(
        {
            "y_true": hotspot_y_nonneg,
            "y_pred": hotspot_pred,
            "season": season_from_timestamp(hotspot_time),
            "week_part": weekpart_from_timestamp(hotspot_time),
            "geography": geography_bin_from_grid_id(hotspot_keys.iloc[:, 0].astype(str)),
        }
    )

    severity_slices = severity_slice_metrics(
        frame=severity_eval_frame,
        top_k_percentile=args.severity_top_k_percentile,
        min_rows=args.min_severity_slice_rows,
    )
    hotspot_slices = hotspot_slice_metrics(
        frame=hotspot_eval_frame,
        min_rows=args.min_hotspot_slice_rows,
    )

    thresholds = GateThresholds(
        min_severity_pr_auc=args.gate_min_severity_pr_auc,
        min_severity_recall_top_k_percentile=args.gate_min_severity_recall_top_k_percentile,
        max_severity_brier=args.gate_max_severity_brier,
        max_hotspot_mae=args.gate_max_hotspot_mae,
        max_hotspot_rmse=args.gate_max_hotspot_rmse,
        max_hotspot_poisson_deviance=args.gate_max_hotspot_poisson_deviance,
        min_hotspot_top_k_hit_rate=args.gate_min_hotspot_top_k_hit_rate,
        min_combined_precision=args.gate_min_combined_precision,
        min_combined_recall=args.gate_min_combined_recall,
        min_combined_join_coverage=args.gate_min_combined_join_coverage,
        max_severity_slice_drop=args.gate_max_severity_slice_drop,
        max_hotspot_slice_rmse_ratio=args.gate_max_hotspot_slice_rmse_ratio,
    )

    stability = evaluate_stability(
        severity_overall_pr_auc=severity_metrics["pr_auc"],
        hotspot_overall_rmse=hotspot_metrics["rmse"],
        severity_slices=severity_slices,
        hotspot_slices=hotspot_slices,
        thresholds=thresholds,
    )
    sanity = run_bias_sanity_checks(
        severity_features=severity_feature_names,
        severity_prob=severity_prob,
        severity_x=severity_aligned,
        hotspot_features=hotspot_feature_names,
        hotspot_pred=hotspot_pred,
        combined_join_coverage=combined_join_coverage,
        min_join_coverage=thresholds.min_combined_join_coverage,
    )
    release_gates = release_gate_rows(
        severity_metrics=severity_metrics,
        hotspot_metrics=hotspot_metrics,
        combined_metrics=combined_metrics,
        stability=stability,
        sanity=sanity,
        thresholds=thresholds,
        poisson_required=poisson_required,
    )

    evaluation_run_dir = (
        args.output_root
        / f"version={args.snapshot_version}"
        / f"extraction_date={resolved_extraction_date}"
    )
    evaluation_run_dir.mkdir(parents=True, exist_ok=True)

    report = build_markdown_report(
        split=args.split,
        run_date=resolved_extraction_date,
        severity_metrics=severity_metrics,
        hotspot_metrics=hotspot_metrics,
        combined_metrics=combined_metrics,
        release_gates=release_gates,
        stability=stability,
        sanity=sanity,
    )
    report_path = evaluation_run_dir / "evaluation_report.md"
    report_path.write_text(report, encoding="utf-8")

    summary: dict[str, Any] = {
        "snapshot_version": args.snapshot_version,
        "extraction_date": resolved_extraction_date,
        "split": args.split,
        "feature_run_dir": str(feature_run_dir),
        "severity_model_run_dir": str(severity_model_run_dir),
        "hotspot_model_run_dir": str(hotspot_model_run_dir),
        "severity_metrics": severity_metrics,
        "hotspot_metrics": hotspot_metrics,
        "combined_operational_metrics": {
            **combined_metrics,
            "combined_join_coverage": combined_join_coverage,
        },
        "release_gates": release_gates,
        "stability_checks": {
            "severity_slices": severity_slices,
            "hotspot_slices": hotspot_slices,
            "result": stability,
        },
        "bias_sanity_checks": sanity,
        "artifacts": {
            "evaluation_report_md": str(report_path),
            "evaluation_metrics_json": str(evaluation_run_dir / "evaluation_metrics.json"),
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    metrics_path = evaluation_run_dir / "evaluation_metrics.json"
    with metrics_path.open("w", encoding="utf-8") as file:
        json.dump(to_json_safe(summary), file, ensure_ascii=True, indent=2, sort_keys=True)

    print(json.dumps(to_json_safe(summary), ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
