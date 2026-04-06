"""Train hotspot forecasting models with rolling-origin backtesting."""

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
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_poisson_deviance, mean_squared_error

EPSILON = 1e-6


@dataclass(frozen=True)
class RollingWindow:
    fold_id: int
    cutoff_time: str
    validation_start: str
    validation_end: str
    train_size: int
    validation_size: int
    train_idx: np.ndarray
    valid_idx: np.ndarray


@dataclass(frozen=True)
class SearchResult:
    params: dict[str, Any]
    fold_count: int
    mean_mae: float
    mean_rmse: float
    mean_poisson_deviance: float
    mean_smape: float


def parse_args() -> argparse.Namespace:
    root_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Train hotspot model with rolling-origin backtesting."
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
        default=root_dir / "artifacts" / "models" / "hotspot",
        help="Output base directory for hotspot model artifacts.",
    )
    parser.add_argument(
        "--snapshot-version",
        type=str,
        default="v1",
        help="Feature snapshot version under --feature-root.",
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
        default="hotspot",
        help="Dataset directory name under the resolved feature run directory.",
    )
    parser.add_argument(
        "--gb-objective",
        choices=["poisson", "tweedie"],
        default="poisson",
        help="Primary global boosting objective.",
    )
    parser.add_argument(
        "--tweedie-variance-power",
        type=float,
        default=1.35,
        help="Variance power used with XGBoost Tweedie objective when available.",
    )
    parser.add_argument(
        "--search-iterations",
        type=int,
        default=24,
        help="Number of sampled hyperparameter candidates for the primary model.",
    )
    parser.add_argument(
        "--time-splits",
        type=int,
        default=5,
        help="Number of rolling-origin cutoff windows for backtesting.",
    )
    parser.add_argument(
        "--min-train-fraction",
        type=float,
        default=0.5,
        help="Minimum chronological fraction reserved for fold training windows.",
    )
    parser.add_argument(
        "--min-validation-rows",
        type=int,
        default=256,
        help="Minimum validation rows required for a cutoff window.",
    )
    parser.add_argument(
        "--seasonal-lag-hours",
        type=int,
        default=24,
        help="Lag in hours used by seasonal-naive baseline.",
    )
    parser.add_argument(
        "--enable-sarima",
        action="store_true",
        help="Enable optional SARIMA overlays for top dense hotspots.",
    )
    parser.add_argument(
        "--sarima-top-n",
        type=int,
        default=10,
        help="Top-N dense grids to consider for SARIMA overlays.",
    )
    parser.add_argument(
        "--enable-prophet",
        action="store_true",
        help="Enable optional Prophet specialization for justified hotspots.",
    )
    parser.add_argument(
        "--prophet-top-n",
        type=int,
        default=8,
        help="Max hotspot grids to specialize with Prophet.",
    )
    parser.add_argument(
        "--prophet-min-grid-points",
        type=int,
        default=200,
        help="Minimum observations per grid before Prophet is considered.",
    )
    parser.add_argument(
        "--prophet-min-holiday-lift",
        type=float,
        default=0.15,
        help="Minimum relative holiday lift required for Prophet eligibility.",
    )
    parser.add_argument(
        "--prophet-min-seasonality-strength",
        type=float,
        default=0.10,
        help="Minimum hourly-seasonality strength required for Prophet eligibility.",
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
    y = coerce_count_target(y_frame[target_col], split_name=split_name)
    return x_frame, y, keys_frame


def coerce_count_target(series: pd.Series, split_name: str) -> np.ndarray:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().any():
        bad_count = int(numeric.isna().sum())
        raise ValueError(
            f"Target contains non-numeric values ({bad_count} rows) in split '{split_name}'."
        )
    if (numeric < 0).any():
        bad_count = int((numeric < 0).sum())
        raise ValueError(f"Target contains negative counts ({bad_count} rows) in split '{split_name}'.")
    return numeric.to_numpy(dtype=float)


def select_time_column(keys_frame: pd.DataFrame) -> str:
    candidates = [
        column for column in keys_frame.columns if "time" in column.lower() or "date" in column.lower()
    ]
    if candidates:
        return candidates[0]
    return keys_frame.columns[-1]


def select_grid_column(keys_frame: pd.DataFrame, time_column: str) -> str:
    candidates = [column for column in keys_frame.columns if column != time_column and "grid" in column.lower()]
    if candidates:
        return candidates[0]
    return keys_frame.columns[0]


def normalize_time_columns(keys_frame: pd.DataFrame, time_column: str) -> pd.DataFrame:
    out = keys_frame.copy()
    parsed = pd.to_datetime(out[time_column], errors="coerce")
    if parsed.isna().any():
        bad_count = int(parsed.isna().sum())
        raise ValueError(
            f"Unable to parse {bad_count} timestamp rows from key column '{time_column}'."
        )
    if getattr(parsed.dt, "tz", None) is not None:
        parsed = parsed.dt.tz_convert(None)
    out[time_column] = parsed
    return out


def build_rolling_origin_windows(
    timestamps: pd.Series,
    n_splits: int,
    min_train_fraction: float,
    min_validation_rows: int,
) -> list[RollingWindow]:
    if n_splits < 2:
        raise ValueError("--time-splits must be >= 2.")
    if not 0.1 <= min_train_fraction < 1.0:
        raise ValueError("--min-train-fraction must be in [0.1, 1.0).")
    if min_validation_rows < 16:
        raise ValueError("--min-validation-rows must be >= 16.")

    unique_times = np.array(sorted(pd.unique(timestamps)))
    unique_count = len(unique_times)
    min_train_unique = max(8, int(round(unique_count * min_train_fraction)))
    min_train_unique = min(min_train_unique, max(unique_count - 2, 1))
    if min_train_unique >= unique_count - 1:
        raise ValueError(
            "Not enough unique timestamps to construct rolling-origin windows. "
            f"Unique times: {unique_count}, min train unique: {min_train_unique}."
        )

    boundaries = np.linspace(min_train_unique, unique_count, n_splits + 1, dtype=int)
    boundaries = np.maximum.accumulate(boundaries)

    windows: list[RollingWindow] = []
    for fold_id in range(n_splits):
        train_end_idx = int(boundaries[fold_id])
        valid_end_idx = int(boundaries[fold_id + 1])
        if valid_end_idx <= train_end_idx:
            continue

        train_end_time = unique_times[train_end_idx - 1]
        valid_start_time = unique_times[train_end_idx]
        valid_end_time = unique_times[valid_end_idx - 1]

        train_mask = timestamps <= train_end_time
        valid_mask = (timestamps >= valid_start_time) & (timestamps <= valid_end_time)
        train_idx = np.where(train_mask.to_numpy())[0]
        valid_idx = np.where(valid_mask.to_numpy())[0]
        if len(valid_idx) < min_validation_rows:
            continue

        windows.append(
            RollingWindow(
                fold_id=fold_id + 1,
                cutoff_time=pd.Timestamp(train_end_time).isoformat(),
                validation_start=pd.Timestamp(valid_start_time).isoformat(),
                validation_end=pd.Timestamp(valid_end_time).isoformat(),
                train_size=int(len(train_idx)),
                validation_size=int(len(valid_idx)),
                train_idx=train_idx,
                valid_idx=valid_idx,
            )
        )

    if not windows:
        raise ValueError(
            "No valid rolling-origin windows were produced. "
            "Try fewer --time-splits, smaller --min-train-fraction, or smaller --min-validation-rows."
        )
    return windows


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
    max_attempts = max(200, iterations * 40)
    attempts = 0
    while len(chosen) < iterations and attempts < max_attempts:
        attempts += 1
        params = {key: rng.choice(search_space[key]) for key in keys}
        signature = tuple(params[key] for key in keys)
        if signature not in chosen:
            chosen[signature] = params
    return list(chosen.values())


def clip_predictions(values: np.ndarray | pd.Series) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = np.where(np.isfinite(arr), arr, np.nan)
    finite = arr[np.isfinite(arr)]
    fallback = float(np.mean(finite)) if len(finite) else 1.0
    arr = np.where(np.isfinite(arr), arr, fallback)
    return np.clip(arr, EPSILON, None)


def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    truth = np.clip(np.asarray(y_true, dtype=float), 0.0, None)
    pred = clip_predictions(y_pred)
    smape = float(np.mean(2.0 * np.abs(pred - truth) / (np.abs(truth) + np.abs(pred) + EPSILON)))
    return {
        "mae": float(mean_absolute_error(truth, pred)),
        "rmse": float(np.sqrt(mean_squared_error(truth, pred))),
        "poisson_deviance": float(mean_poisson_deviance(truth, pred)),
        "smape": smape,
    }


def aggregate_metrics(metric_rows: list[dict[str, float]]) -> dict[str, float]:
    if not metric_rows:
        raise ValueError("Cannot aggregate an empty metric list.")
    keys = sorted(metric_rows[0].keys())
    return {key: float(np.mean([row[key] for row in metric_rows])) for key in keys}


def _import_xgboost() -> Any | None:
    try:
        import xgboost as xgb
    except ImportError:
        return None
    return xgb


def _import_sarimax() -> Any | None:
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
    except ImportError:
        return None
    return SARIMAX


def _import_prophet() -> Any | None:
    try:
        from prophet import Prophet
    except ImportError:
        return None
    return Prophet


def resolve_primary_family(requested_objective: str) -> tuple[str, str | None]:
    if requested_objective == "poisson":
        return "hist_gradient_boosting_poisson", None

    xgb = _import_xgboost()
    if xgb is not None:
        return "xgboost_tweedie", None
    return (
        "hist_gradient_boosting_poisson",
        "Tweedie objective was requested but xgboost is not installed; "
        "falling back to HistGradientBoostingRegressor with Poisson loss.",
    )


def build_primary_model(
    family: str,
    params: dict[str, Any],
    seed: int,
    n_jobs: int,
    tweedie_variance_power: float,
) -> Any:
    if family == "hist_gradient_boosting_poisson":
        return HistGradientBoostingRegressor(
            loss="poisson",
            random_state=seed,
            **params,
        )
    if family == "xgboost_tweedie":
        xgb = _import_xgboost()
        if xgb is None:
            raise ImportError("xgboost is required for Tweedie boosting and is not installed.")
        return xgb.XGBRegressor(
            objective="reg:tweedie",
            eval_metric="poisson-nloglik",
            tree_method="hist",
            random_state=seed,
            n_jobs=n_jobs,
            tweedie_variance_power=tweedie_variance_power,
            **params,
        )
    raise ValueError(f"Unsupported model family: {family}")


def primary_search_space(family: str) -> dict[str, list[Any]]:
    if family == "hist_gradient_boosting_poisson":
        return {
            "max_iter": [250, 400, 600, 800],
            "learning_rate": [0.03, 0.05, 0.08, 0.12],
            "max_leaf_nodes": [31, 63, 127],
            "max_depth": [None, 6, 10],
            "min_samples_leaf": [20, 50, 100],
            "l2_regularization": [0.0, 0.1, 1.0, 3.0],
        }
    if family == "xgboost_tweedie":
        return {
            "n_estimators": [250, 400, 600, 800],
            "max_depth": [3, 4, 6, 8],
            "learning_rate": [0.03, 0.05, 0.08, 0.12],
            "subsample": [0.7, 0.85, 1.0],
            "colsample_bytree": [0.7, 0.85, 1.0],
            "min_child_weight": [1, 3, 7],
            "reg_lambda": [1.0, 3.0, 6.0, 10.0],
        }
    raise ValueError(f"Unsupported model family: {family}")


def fit_predict_primary(
    *,
    x_frame: pd.DataFrame,
    y: np.ndarray,
    train_idx: np.ndarray,
    valid_idx: np.ndarray,
    family: str,
    params: dict[str, Any],
    base_seed: int,
    fold_seed_offset: int,
    n_jobs: int,
    tweedie_variance_power: float,
) -> np.ndarray:
    seed = base_seed + fold_seed_offset
    model = build_primary_model(
        family=family,
        params=params,
        seed=seed,
        n_jobs=n_jobs,
        tweedie_variance_power=tweedie_variance_power,
    )
    model.fit(x_frame.iloc[train_idx], y[train_idx])
    pred = model.predict(x_frame.iloc[valid_idx])
    return clip_predictions(pred)


def search_primary_model(
    *,
    x_frame: pd.DataFrame,
    y: np.ndarray,
    windows: list[RollingWindow],
    family: str,
    search_iterations: int,
    seed: int,
    n_jobs: int,
    tweedie_variance_power: float,
) -> tuple[dict[str, Any], list[SearchResult]]:
    candidates = sample_hyperparameters(
        search_space=primary_search_space(family),
        iterations=search_iterations,
        seed=seed,
    )
    ranked: list[SearchResult] = []
    for candidate_id, params in enumerate(candidates):
        fold_metrics: list[dict[str, float]] = []
        for fold in windows:
            preds = fit_predict_primary(
                x_frame=x_frame,
                y=y,
                train_idx=fold.train_idx,
                valid_idx=fold.valid_idx,
                family=family,
                params=params,
                base_seed=seed + candidate_id * 1000,
                fold_seed_offset=fold.fold_id,
                n_jobs=n_jobs,
                tweedie_variance_power=tweedie_variance_power,
            )
            fold_metrics.append(compute_regression_metrics(y[fold.valid_idx], preds))
        if not fold_metrics:
            continue
        ranked.append(
            SearchResult(
                params=params,
                fold_count=len(fold_metrics),
                mean_mae=float(np.mean([m["mae"] for m in fold_metrics])),
                mean_rmse=float(np.mean([m["rmse"] for m in fold_metrics])),
                mean_poisson_deviance=float(np.mean([m["poisson_deviance"] for m in fold_metrics])),
                mean_smape=float(np.mean([m["smape"] for m in fold_metrics])),
            )
        )

    if not ranked:
        raise RuntimeError("Primary model search produced no valid candidates.")

    ranked = sorted(
        ranked,
        key=lambda result: (
            result.mean_poisson_deviance,
            result.mean_rmse,
            result.mean_mae,
            result.mean_smape,
        ),
    )
    return ranked[0].params, ranked


def infer_time_step(timestamps: pd.Series) -> pd.Timedelta:
    ordered = np.array(sorted(pd.unique(timestamps)))
    if len(ordered) < 2:
        return pd.Timedelta(hours=1)
    deltas = np.diff(ordered).astype("timedelta64[s]").astype(np.int64)
    positive = deltas[deltas > 0]
    if len(positive) == 0:
        return pd.Timedelta(hours=1)
    seconds = int(pd.Series(positive).mode().iloc[0])
    return pd.Timedelta(seconds=seconds)


def timedelta_to_freq(delta: pd.Timedelta) -> str:
    seconds = max(int(delta.total_seconds()), 1)
    if seconds % 3600 == 0:
        hours = max(seconds // 3600, 1)
        return f"{hours}h"
    if seconds % 60 == 0:
        minutes = max(seconds // 60, 1)
        return f"{minutes}min"
    return f"{seconds}s"


def seasonal_naive_predict(
    *,
    keys_history: pd.DataFrame,
    y_history: np.ndarray,
    keys_future: pd.DataFrame,
    grid_column: str,
    time_column: str,
    seasonal_lag: pd.Timedelta,
) -> np.ndarray:
    if len(keys_history) == 0:
        return np.full(len(keys_future), 1.0, dtype=float)

    history = keys_history[[grid_column, time_column]].copy()
    history["target"] = np.asarray(y_history, dtype=float)
    history[grid_column] = history[grid_column].astype(str)
    history = (
        history.groupby([grid_column, time_column], as_index=False)["target"]
        .sum()
        .sort_values([grid_column, time_column])
    )

    lookup = history.set_index([grid_column, time_column])["target"]
    grid_means = history.groupby(grid_column)["target"].mean().to_dict()
    global_mean = float(history["target"].mean()) if len(history) else 1.0

    future = keys_future[[grid_column, time_column]].copy()
    future[grid_column] = future[grid_column].astype(str)
    preds = np.zeros(len(future), dtype=float)
    for pos, (_, row) in enumerate(future.iterrows()):
        grid_id = row[grid_column]
        timestamp = row[time_column]
        lag_value = lookup.get((grid_id, timestamp - seasonal_lag))
        if lag_value is not None:
            preds[pos] = float(lag_value)
            continue
        if grid_id in grid_means:
            preds[pos] = float(grid_means[grid_id])
            continue
        preds[pos] = global_mean
    return clip_predictions(preds)


def select_dense_grids(keys_frame: pd.DataFrame, y: np.ndarray, grid_column: str, top_n: int) -> list[str]:
    density = (
        pd.DataFrame({grid_column: keys_frame[grid_column].astype(str), "target": np.asarray(y, dtype=float)})
        .groupby(grid_column, as_index=False)["target"]
        .sum()
        .sort_values("target", ascending=False)
    )
    return density[grid_column].head(top_n).tolist()


def _build_regular_series(
    timestamps: pd.Series,
    values: np.ndarray,
    start: pd.Timestamp,
    end: pd.Timestamp,
    freq: str,
) -> pd.Series:
    full_index = pd.date_range(start=start, end=end, freq=freq)
    series = pd.Series(0.0, index=full_index, dtype=float)
    frame = pd.DataFrame({"ts": timestamps, "target": values})
    collapsed = frame.groupby("ts", as_index=False)["target"].sum()
    collapsed = collapsed[collapsed["ts"].isin(series.index)]
    series.loc[collapsed["ts"]] = collapsed["target"].to_numpy(dtype=float)
    return series


def _fit_sarima_forecast(
    *,
    sarimax_cls: Any,
    train_times: pd.Series,
    train_values: np.ndarray,
    future_times: pd.Series,
    freq: str,
    seasonal_periods: int,
) -> pd.Series | None:
    if len(train_times) < max(32, seasonal_periods * 2):
        return None
    train_start = pd.Timestamp(train_times.min())
    train_end = pd.Timestamp(train_times.max())
    future_end = pd.Timestamp(future_times.max())
    if future_end <= train_end:
        return None

    train_series = _build_regular_series(
        timestamps=train_times,
        values=train_values,
        start=train_start,
        end=train_end,
        freq=freq,
    )
    seasonal_order = (1, 0, 1, seasonal_periods) if seasonal_periods > 1 else (0, 0, 0, 0)

    try:
        model = sarimax_cls(
            train_series,
            order=(1, 0, 1),
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fitted = model.fit(disp=False)
        future_index = pd.Index(sorted(pd.unique(future_times)))
        pred = fitted.get_prediction(start=future_index.min(), end=future_index.max()).predicted_mean
        return pred.reindex(future_index)
    except Exception:
        return None


def sarima_overlay_predict(
    *,
    base_predictions: np.ndarray,
    keys_history: pd.DataFrame,
    y_history: np.ndarray,
    keys_future: pd.DataFrame,
    grid_column: str,
    time_column: str,
    top_n: int,
    seasonal_periods: int,
    freq: str,
) -> tuple[np.ndarray, list[str], int, list[str]]:
    sarimax_cls = _import_sarimax()
    if sarimax_cls is None:
        return (
            clip_predictions(base_predictions),
            [],
            0,
            ["statsmodels is not installed, SARIMA overlay skipped."],
        )

    preds = clip_predictions(base_predictions).copy()
    dense_grids = select_dense_grids(keys_history, y_history, grid_column=grid_column, top_n=top_n)
    failures: list[str] = []
    successful = 0

    history = keys_history[[grid_column, time_column]].copy()
    history[grid_column] = history[grid_column].astype(str)
    future = keys_future[[grid_column, time_column]].copy()
    future[grid_column] = future[grid_column].astype(str)
    target_history = np.asarray(y_history, dtype=float)

    for grid_id in dense_grids:
        train_mask = history[grid_column] == grid_id
        valid_mask = future[grid_column] == grid_id
        if not bool(valid_mask.any()):
            continue

        train_times = history.loc[train_mask, time_column]
        train_values = target_history[train_mask.to_numpy()]
        future_times = future.loc[valid_mask, time_column]
        if len(train_times) < max(32, seasonal_periods * 2):
            failures.append(f"{grid_id}: insufficient history for SARIMA.")
            continue

        forecast = _fit_sarima_forecast(
            sarimax_cls=sarimax_cls,
            train_times=train_times,
            train_values=train_values,
            future_times=future_times,
            freq=freq,
            seasonal_periods=seasonal_periods,
        )
        if forecast is None:
            failures.append(f"{grid_id}: SARIMA fit failed.")
            continue

        idx = np.where(valid_mask.to_numpy())[0]
        mapped = future_times.map(forecast).to_numpy(dtype=float)
        good = np.isfinite(mapped)
        if not np.any(good):
            failures.append(f"{grid_id}: SARIMA produced no usable forecasts.")
            continue
        preds[idx[good]] = clip_predictions(mapped[good])
        successful += 1

    return clip_predictions(preds), dense_grids, successful, failures


def extract_holiday_flags(x_frame: pd.DataFrame) -> np.ndarray:
    lower_map = {column.lower(): column for column in x_frame.columns}
    true_candidates = [column for column in x_frame.columns if column.lower().startswith("is_holiday=") and "true" in column.lower()]
    false_candidates = [column for column in x_frame.columns if column.lower().startswith("is_holiday=") and "false" in column.lower()]

    if true_candidates:
        series = pd.to_numeric(x_frame[true_candidates[0]], errors="coerce").fillna(0.0)
        return (series.to_numpy(dtype=float) > 0.0).astype(bool)
    if false_candidates:
        series = pd.to_numeric(x_frame[false_candidates[0]], errors="coerce").fillna(0.0)
        return (series.to_numpy(dtype=float) <= 0.0).astype(bool)
    if "is_holiday" in lower_map:
        series = x_frame[lower_map["is_holiday"]]
        if pd.api.types.is_bool_dtype(series):
            return series.to_numpy(dtype=bool)
        numeric = pd.to_numeric(series, errors="coerce").fillna(0.0).to_numpy(dtype=float)
        return (numeric > 0.0).astype(bool)
    return np.zeros(len(x_frame), dtype=bool)


def select_prophet_grids(
    *,
    keys_history: pd.DataFrame,
    y_history: np.ndarray,
    x_history: pd.DataFrame,
    grid_column: str,
    time_column: str,
    top_n: int,
    min_points: int,
    min_holiday_lift: float,
    min_seasonality_strength: float,
) -> tuple[list[str], list[dict[str, Any]]]:
    holiday_flags = extract_holiday_flags(x_history)
    frame = keys_history[[grid_column, time_column]].copy()
    frame[grid_column] = frame[grid_column].astype(str)
    frame["target"] = np.asarray(y_history, dtype=float)
    frame["holiday"] = holiday_flags
    frame["hour"] = frame[time_column].dt.hour

    diagnostics: list[dict[str, Any]] = []
    for grid_id, group in frame.groupby(grid_column):
        rows = int(len(group))
        if rows < min_points:
            continue
        holiday_part = group[group["holiday"]]
        nonholiday_part = group[~group["holiday"]]
        holiday_mean = float(holiday_part["target"].mean()) if len(holiday_part) else 0.0
        nonholiday_mean = float(nonholiday_part["target"].mean()) if len(nonholiday_part) else 0.0
        holiday_lift = ((holiday_mean + EPSILON) / (nonholiday_mean + EPSILON)) - 1.0

        hourly_mean = group.groupby("hour")["target"].mean()
        seasonality_strength = float(hourly_mean.std(ddof=0) / (group["target"].mean() + EPSILON))
        justified = holiday_lift >= min_holiday_lift or seasonality_strength >= min_seasonality_strength
        diagnostics.append(
            {
                "grid_id": grid_id,
                "rows": rows,
                "total_count": float(group["target"].sum()),
                "holiday_lift": float(holiday_lift),
                "seasonality_strength": float(seasonality_strength),
                "justified": bool(justified),
            }
        )

    eligible = [item for item in diagnostics if item["justified"]]
    eligible = sorted(
        eligible,
        key=lambda item: (item["total_count"], item["holiday_lift"], item["seasonality_strength"]),
        reverse=True,
    )
    selected_grids = [item["grid_id"] for item in eligible[:top_n]]
    return selected_grids, diagnostics


def _fit_prophet_forecast(
    *,
    prophet_cls: Any,
    train_times: pd.Series,
    train_values: np.ndarray,
    future_times: pd.Series,
    holiday_times: pd.Series,
    freq: str,
    include_daily: bool,
) -> pd.Series | None:
    if len(train_times) < 72:
        return None

    train_start = pd.Timestamp(train_times.min())
    train_end = pd.Timestamp(train_times.max())
    train_series = _build_regular_series(
        timestamps=train_times,
        values=train_values,
        start=train_start,
        end=train_end,
        freq=freq,
    )
    train_df = pd.DataFrame({"ds": train_series.index, "y": train_series.values})

    holidays_df: pd.DataFrame | None = None
    unique_holidays = pd.Index(sorted(pd.unique(holiday_times)))
    if len(unique_holidays) > 0:
        holidays_df = pd.DataFrame(
            {
                "holiday": ["calendar_holiday"] * len(unique_holidays),
                "ds": unique_holidays,
            }
        )

    try:
        model = prophet_cls(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=include_daily,
            holidays=holidays_df,
        )
        model.fit(train_df)
        future_unique = pd.Index(sorted(pd.unique(future_times)))
        future_df = pd.DataFrame({"ds": future_unique})
        forecast = model.predict(future_df)
        return forecast.set_index("ds")["yhat"].reindex(future_unique)
    except Exception:
        return None


def prophet_overlay_predict(
    *,
    base_predictions: np.ndarray,
    keys_history: pd.DataFrame,
    y_history: np.ndarray,
    x_history: pd.DataFrame,
    keys_future: pd.DataFrame,
    x_future: pd.DataFrame,
    grid_column: str,
    time_column: str,
    freq: str,
    top_n: int,
    min_points: int,
    min_holiday_lift: float,
    min_seasonality_strength: float,
) -> tuple[np.ndarray, list[str], int, list[str], list[dict[str, Any]]]:
    prophet_cls = _import_prophet()
    if prophet_cls is None:
        return (
            clip_predictions(base_predictions),
            [],
            0,
            ["prophet is not installed, Prophet specialization skipped."],
            [],
        )

    selected_grids, diagnostics = select_prophet_grids(
        keys_history=keys_history,
        y_history=y_history,
        x_history=x_history,
        grid_column=grid_column,
        time_column=time_column,
        top_n=top_n,
        min_points=min_points,
        min_holiday_lift=min_holiday_lift,
        min_seasonality_strength=min_seasonality_strength,
    )
    if not selected_grids:
        return clip_predictions(base_predictions), [], 0, [], diagnostics

    preds = clip_predictions(base_predictions).copy()
    failures: list[str] = []
    successful = 0

    holiday_hist = extract_holiday_flags(x_history)
    holiday_future = extract_holiday_flags(x_future)
    history = keys_history[[grid_column, time_column]].copy()
    history[grid_column] = history[grid_column].astype(str)
    future = keys_future[[grid_column, time_column]].copy()
    future[grid_column] = future[grid_column].astype(str)
    target_history = np.asarray(y_history, dtype=float)

    freq_lower = freq.lower()
    include_daily = ("h" in freq_lower) or ("min" in freq_lower and not freq_lower.startswith("1440"))

    for grid_id in selected_grids:
        train_mask = history[grid_column] == grid_id
        valid_mask = future[grid_column] == grid_id
        if not bool(valid_mask.any()):
            continue

        train_times = history.loc[train_mask, time_column]
        train_values = target_history[train_mask.to_numpy()]
        future_times = future.loc[valid_mask, time_column]
        holiday_times = pd.concat(
            [
                history.loc[train_mask.to_numpy() & holiday_hist, time_column],
                future.loc[valid_mask.to_numpy() & holiday_future, time_column],
            ],
            ignore_index=True,
        )

        forecast = _fit_prophet_forecast(
            prophet_cls=prophet_cls,
            train_times=train_times,
            train_values=train_values,
            future_times=future_times,
            holiday_times=holiday_times,
            freq=freq,
            include_daily=include_daily,
        )
        if forecast is None:
            failures.append(f"{grid_id}: Prophet fit failed.")
            continue

        idx = np.where(valid_mask.to_numpy())[0]
        mapped = future_times.map(forecast).to_numpy(dtype=float)
        good = np.isfinite(mapped)
        if not np.any(good):
            failures.append(f"{grid_id}: Prophet produced no usable forecasts.")
            continue
        preds[idx[good]] = clip_predictions(mapped[good])
        successful += 1

    return clip_predictions(preds), selected_grids, successful, failures, diagnostics


def render_metrics_table(rows: list[tuple[str, dict[str, float]]]) -> str:
    header = "| Model | MAE | RMSE | Poisson Deviance | sMAPE |"
    divider = "| --- | ---: | ---: | ---: | ---: |"
    lines = [header, divider]
    for label, metrics in rows:
        lines.append(
            "| "
            f"{label} | "
            f"{metrics['mae']:.4f} | "
            f"{metrics['rmse']:.4f} | "
            f"{metrics['poisson_deviance']:.4f} | "
            f"{metrics['smape']:.4f} |"
        )
    return "\n".join(lines)


def render_windows_table(windows: list[RollingWindow]) -> str:
    header = "| Fold | Cutoff | Validation Start | Validation End | Train Rows | Validation Rows |"
    divider = "| ---: | --- | --- | --- | ---: | ---: |"
    lines = [header, divider]
    for window in windows:
        lines.append(
            "| "
            f"{window.fold_id} | "
            f"{window.cutoff_time} | "
            f"{window.validation_start} | "
            f"{window.validation_end} | "
            f"{window.train_size} | "
            f"{window.validation_size} |"
        )
    return "\n".join(lines)


def build_training_report(
    *,
    output_run_dir: Path,
    feature_run_dir: Path,
    dataset_dir: Path,
    primary_family: str,
    requested_objective: str,
    objective_fallback_note: str | None,
    feature_count: int,
    split_sizes: dict[str, int],
    windows: list[RollingWindow],
    backtest_metrics: dict[str, dict[str, float]],
    holdout_metrics: dict[str, dict[str, float]],
    best_params: dict[str, Any],
    search_ranked: list[SearchResult],
    seasonal_lag_hours: int,
    sarima_info: dict[str, Any],
    prophet_info: dict[str, Any],
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    top_candidates = search_ranked[: min(5, len(search_ranked))]
    candidate_lines = []
    for rank, candidate in enumerate(top_candidates, start=1):
        candidate_lines.append(
            f"{rank}. `poisson_dev={candidate.mean_poisson_deviance:.5f}`, "
            f"`rmse={candidate.mean_rmse:.5f}`, "
            f"`mae={candidate.mean_mae:.5f}`, "
            f"`smape={candidate.mean_smape:.5f}` with params `{json.dumps(candidate.params, sort_keys=True)}`"
        )

    optional_notes: list[str] = []
    if objective_fallback_note:
        optional_notes.append(f"- Objective fallback: {objective_fallback_note}")
    if sarima_info.get("notes"):
        optional_notes.extend([f"- SARIMA: {note}" for note in sarima_info["notes"]])
    if prophet_info.get("notes"):
        optional_notes.extend([f"- Prophet: {note}" for note in prophet_info["notes"]])

    report = [
        "# Hotspot Training Report",
        "",
        "## Run Summary",
        f"- Generated at (UTC): `{generated_at}`",
        f"- Feature run directory: `{feature_run_dir}`",
        f"- Dataset directory: `{dataset_dir}`",
        f"- Output directory: `{output_run_dir}`",
        f"- Requested objective: `{requested_objective}`",
        f"- Resolved primary model family: `{primary_family}`",
        f"- Feature count: `{feature_count}`",
        f"- Seasonal-naive lag (hours): `{seasonal_lag_hours}`",
        f"- Split sizes: train={split_sizes['train']}, validation={split_sizes['validation']}, test={split_sizes['test']}",
        "",
        "## Rolling-Origin Windows",
        render_windows_table(windows),
        "",
        "## Rolling-Origin Backtesting (Train Split)",
        render_metrics_table([(label, metrics) for label, metrics in backtest_metrics.items()]),
        "",
        "## Holdout Test Metrics (Train+Validation fit, Test evaluation)",
        render_metrics_table([(label, metrics) for label, metrics in holdout_metrics.items()]),
        "",
        "## Primary Hyperparameter Search",
        f"- Best params: `{json.dumps(best_params, sort_keys=True)}`",
        f"- Candidates evaluated: `{len(search_ranked)}`",
        "- Top candidates:",
        *[f"  {line}" for line in candidate_lines],
        "",
        "## Optional Models",
        f"- SARIMA enabled: `{sarima_info['enabled']}`",
        f"- SARIMA available: `{sarima_info['available']}`",
        f"- SARIMA dense grids considered (holdout): `{sarima_info.get('dense_grids', [])}`",
        f"- SARIMA successful holdout overlays: `{sarima_info.get('successful_holdout_overlays', 0)}`",
        f"- Prophet enabled: `{prophet_info['enabled']}`",
        f"- Prophet available: `{prophet_info['available']}`",
        f"- Prophet selected grids (holdout): `{prophet_info.get('selected_grids', [])}`",
        f"- Prophet successful holdout overlays: `{prophet_info.get('successful_holdout_overlays', 0)}`",
        "",
        "## Notes",
        *(optional_notes if optional_notes else ["- None."]),
        "",
        "## Exported Artifacts",
        "- `hotspot_model.pkl`",
        "- `hotspot_feature_list.json`",
        "- `hotspot_training_report.md`",
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
    x_val, y_val, keys_val = load_split_dataset(dataset_dir, "validation")
    x_test, y_test, keys_test = load_split_dataset(dataset_dir, "test")
    if x_train.empty or x_val.empty or x_test.empty:
        raise ValueError("One or more feature splits are empty.")

    feature_columns = list(x_train.columns)
    x_val = x_val.reindex(columns=feature_columns, fill_value=0)
    x_test = x_test.reindex(columns=feature_columns, fill_value=0)

    time_column = select_time_column(keys_train)
    grid_column = select_grid_column(keys_train, time_column=time_column)
    keys_train = normalize_time_columns(keys_train, time_column=time_column)
    keys_val = normalize_time_columns(keys_val, time_column=time_column)
    keys_test = normalize_time_columns(keys_test, time_column=time_column)
    keys_train[grid_column] = keys_train[grid_column].astype(str)
    keys_val[grid_column] = keys_val[grid_column].astype(str)
    keys_test[grid_column] = keys_test[grid_column].astype(str)

    windows = build_rolling_origin_windows(
        timestamps=keys_train[time_column],
        n_splits=args.time_splits,
        min_train_fraction=args.min_train_fraction,
        min_validation_rows=args.min_validation_rows,
    )

    requested_objective = args.gb_objective
    primary_family, objective_fallback_note = resolve_primary_family(requested_objective)
    best_params, ranked_search = search_primary_model(
        x_frame=x_train,
        y=y_train,
        windows=windows,
        family=primary_family,
        search_iterations=args.search_iterations,
        seed=args.random_seed,
        n_jobs=args.n_jobs,
        tweedie_variance_power=args.tweedie_variance_power,
    )

    time_step = infer_time_step(keys_train[time_column])
    freq = timedelta_to_freq(time_step)
    seasonal_lag = pd.Timedelta(hours=args.seasonal_lag_hours)
    seasonal_periods = max(int(round(seasonal_lag / time_step)), 1)

    seasonal_fold_metrics: list[dict[str, float]] = []
    primary_fold_metrics: list[dict[str, float]] = []
    sarima_fold_metrics: list[dict[str, float]] = []
    prophet_fold_metrics: list[dict[str, float]] = []

    sarima_notes: list[str] = []
    prophet_notes: list[str] = []
    sarima_available = _import_sarimax() is not None
    prophet_available = _import_prophet() is not None

    for window in windows:
        keys_hist = keys_train.iloc[window.train_idx].reset_index(drop=True)
        y_hist = y_train[window.train_idx]
        keys_future = keys_train.iloc[window.valid_idx].reset_index(drop=True)
        x_hist = x_train.iloc[window.train_idx].reset_index(drop=True)
        x_future = x_train.iloc[window.valid_idx].reset_index(drop=True)
        y_future = y_train[window.valid_idx]

        baseline_pred = seasonal_naive_predict(
            keys_history=keys_hist,
            y_history=y_hist,
            keys_future=keys_future,
            grid_column=grid_column,
            time_column=time_column,
            seasonal_lag=seasonal_lag,
        )
        seasonal_fold_metrics.append(compute_regression_metrics(y_future, baseline_pred))

        primary_pred = fit_predict_primary(
            x_frame=x_train,
            y=y_train,
            train_idx=window.train_idx,
            valid_idx=window.valid_idx,
            family=primary_family,
            params=best_params,
            base_seed=args.random_seed + 91000,
            fold_seed_offset=window.fold_id,
            n_jobs=args.n_jobs,
            tweedie_variance_power=args.tweedie_variance_power,
        )
        primary_fold_metrics.append(compute_regression_metrics(y_future, primary_pred))

        if args.enable_sarima:
            sarima_pred, _dense, success_count, failures = sarima_overlay_predict(
                base_predictions=baseline_pred,
                keys_history=keys_hist,
                y_history=y_hist,
                keys_future=keys_future,
                grid_column=grid_column,
                time_column=time_column,
                top_n=args.sarima_top_n,
                seasonal_periods=seasonal_periods,
                freq=freq,
            )
            if failures:
                sarima_notes.extend([f"fold {window.fold_id}: {item}" for item in failures[:4]])
            if success_count == 0:
                sarima_notes.append(f"fold {window.fold_id}: no successful SARIMA overlays.")
            sarima_fold_metrics.append(compute_regression_metrics(y_future, sarima_pred))

        if args.enable_prophet:
            prophet_pred, _selected, success_count, failures, _diag = prophet_overlay_predict(
                base_predictions=primary_pred,
                keys_history=keys_hist,
                y_history=y_hist,
                x_history=x_hist,
                keys_future=keys_future,
                x_future=x_future,
                grid_column=grid_column,
                time_column=time_column,
                freq=freq,
                top_n=args.prophet_top_n,
                min_points=args.prophet_min_grid_points,
                min_holiday_lift=args.prophet_min_holiday_lift,
                min_seasonality_strength=args.prophet_min_seasonality_strength,
            )
            if failures:
                prophet_notes.extend([f"fold {window.fold_id}: {item}" for item in failures[:4]])
            if success_count == 0:
                prophet_notes.append(f"fold {window.fold_id}: no successful Prophet overlays.")
            prophet_fold_metrics.append(compute_regression_metrics(y_future, prophet_pred))

    backtest_metrics: dict[str, dict[str, float]] = {
        "Seasonal Naive": aggregate_metrics(seasonal_fold_metrics),
        "Primary Global Boosting": aggregate_metrics(primary_fold_metrics),
    }
    if sarima_fold_metrics:
        backtest_metrics["Seasonal Naive + SARIMA Overlay"] = aggregate_metrics(sarima_fold_metrics)
    if prophet_fold_metrics:
        backtest_metrics["Primary + Prophet Specialization"] = aggregate_metrics(prophet_fold_metrics)

    x_trainval = pd.concat([x_train, x_val], axis=0, ignore_index=True)
    y_trainval = np.concatenate([y_train, y_val], axis=0)
    keys_trainval = pd.concat([keys_train, keys_val], axis=0, ignore_index=True)

    baseline_test_pred = seasonal_naive_predict(
        keys_history=keys_trainval,
        y_history=y_trainval,
        keys_future=keys_test,
        grid_column=grid_column,
        time_column=time_column,
        seasonal_lag=seasonal_lag,
    )
    baseline_test_metrics = compute_regression_metrics(y_test, baseline_test_pred)

    primary_model = build_primary_model(
        family=primary_family,
        params=best_params,
        seed=args.random_seed,
        n_jobs=args.n_jobs,
        tweedie_variance_power=args.tweedie_variance_power,
    )
    primary_model.fit(x_trainval, y_trainval)
    primary_test_pred = clip_predictions(primary_model.predict(x_test))
    primary_test_metrics = compute_regression_metrics(y_test, primary_test_pred)

    sarima_dense_grids: list[str] = []
    sarima_success_holdout = 0
    sarima_test_metrics: dict[str, float] | None = None
    if args.enable_sarima:
        sarima_test_pred, sarima_dense_grids, sarima_success_holdout, failures = sarima_overlay_predict(
            base_predictions=baseline_test_pred,
            keys_history=keys_trainval,
            y_history=y_trainval,
            keys_future=keys_test,
            grid_column=grid_column,
            time_column=time_column,
            top_n=args.sarima_top_n,
            seasonal_periods=seasonal_periods,
            freq=freq,
        )
        if failures:
            sarima_notes.extend([f"holdout: {item}" for item in failures[:6]])
        sarima_test_metrics = compute_regression_metrics(y_test, sarima_test_pred)

    prophet_selected_grids: list[str] = []
    prophet_success_holdout = 0
    prophet_test_metrics: dict[str, float] | None = None
    prophet_diagnostics: list[dict[str, Any]] = []
    if args.enable_prophet:
        prophet_test_pred, prophet_selected_grids, prophet_success_holdout, failures, diagnostics = (
            prophet_overlay_predict(
                base_predictions=primary_test_pred,
                keys_history=keys_trainval,
                y_history=y_trainval,
                x_history=x_trainval,
                keys_future=keys_test,
                x_future=x_test,
                grid_column=grid_column,
                time_column=time_column,
                freq=freq,
                top_n=args.prophet_top_n,
                min_points=args.prophet_min_grid_points,
                min_holiday_lift=args.prophet_min_holiday_lift,
                min_seasonality_strength=args.prophet_min_seasonality_strength,
            )
        )
        prophet_diagnostics = diagnostics
        if failures:
            prophet_notes.extend([f"holdout: {item}" for item in failures[:6]])
        prophet_test_metrics = compute_regression_metrics(y_test, prophet_test_pred)

    holdout_metrics: dict[str, dict[str, float]] = {
        "Seasonal Naive": baseline_test_metrics,
        "Primary Global Boosting": primary_test_metrics,
    }
    if sarima_test_metrics is not None:
        holdout_metrics["Seasonal Naive + SARIMA Overlay"] = sarima_test_metrics
    if prophet_test_metrics is not None:
        holdout_metrics["Primary + Prophet Specialization"] = prophet_test_metrics

    output_run_dir = (
        args.output_root
        / f"version={args.snapshot_version}"
        / f"extraction_date={resolved_extraction_date}"
    )
    output_run_dir.mkdir(parents=True, exist_ok=True)

    feature_list_path = output_run_dir / "hotspot_feature_list.json"
    model_path = output_run_dir / "hotspot_model.pkl"
    report_path = output_run_dir / "hotspot_training_report.md"

    with feature_list_path.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "feature_count": int(len(feature_columns)),
                "features": feature_columns,
                "target": "crash_count",
                "grid_column": grid_column,
                "time_column": time_column,
            },
            file,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )

    model_bundle = {
        "model_type": "hotspot_forecasting_bundle",
        "requested_objective": requested_objective,
        "resolved_primary_family": primary_family,
        "objective_fallback_note": objective_fallback_note,
        "best_params": best_params,
        "primary_model": primary_model,
        "feature_names": feature_columns,
        "grid_column": grid_column,
        "time_column": time_column,
        "seasonal_naive": {
            "lag_hours": args.seasonal_lag_hours,
            "inferred_time_step_seconds": int(time_step.total_seconds()),
            "seasonal_periods": int(seasonal_periods),
        },
        "optional_models": {
            "sarima": {
                "enabled": bool(args.enable_sarima),
                "available": bool(sarima_available),
                "top_n": int(args.sarima_top_n),
                "dense_grids": sarima_dense_grids,
                "successful_holdout_overlays": int(sarima_success_holdout),
            },
            "prophet": {
                "enabled": bool(args.enable_prophet),
                "available": bool(prophet_available),
                "top_n": int(args.prophet_top_n),
                "selected_grids": prophet_selected_grids,
                "successful_holdout_overlays": int(prophet_success_holdout),
                "diagnostics": prophet_diagnostics[:25],
            },
        },
        "backtesting": {
            "window_count": int(len(windows)),
            "windows": [
                {
                    "fold_id": int(window.fold_id),
                    "cutoff_time": window.cutoff_time,
                    "validation_start": window.validation_start,
                    "validation_end": window.validation_end,
                    "train_size": int(window.train_size),
                    "validation_size": int(window.validation_size),
                }
                for window in windows
            ],
            "metrics": backtest_metrics,
        },
        "holdout_metrics": holdout_metrics,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    with model_path.open("wb") as file:
        pickle.dump(model_bundle, file, protocol=pickle.HIGHEST_PROTOCOL)

    sarima_info = {
        "enabled": bool(args.enable_sarima),
        "available": bool(sarima_available),
        "dense_grids": sarima_dense_grids,
        "successful_holdout_overlays": int(sarima_success_holdout),
        "notes": sarima_notes[:20],
    }
    prophet_info = {
        "enabled": bool(args.enable_prophet),
        "available": bool(prophet_available),
        "selected_grids": prophet_selected_grids,
        "successful_holdout_overlays": int(prophet_success_holdout),
        "notes": prophet_notes[:20],
    }

    report_text = build_training_report(
        output_run_dir=output_run_dir,
        feature_run_dir=feature_run_dir,
        dataset_dir=dataset_dir,
        primary_family=primary_family,
        requested_objective=requested_objective,
        objective_fallback_note=objective_fallback_note,
        feature_count=int(len(feature_columns)),
        split_sizes={
            "train": int(len(x_train)),
            "validation": int(len(x_val)),
            "test": int(len(x_test)),
        },
        windows=windows,
        backtest_metrics=backtest_metrics,
        holdout_metrics=holdout_metrics,
        best_params=best_params,
        search_ranked=ranked_search,
        seasonal_lag_hours=args.seasonal_lag_hours,
        sarima_info=sarima_info,
        prophet_info=prophet_info,
    )
    with report_path.open("w", encoding="utf-8") as file:
        file.write(report_text)

    summary = {
        "feature_run_dir": str(feature_run_dir),
        "dataset_dir": str(dataset_dir),
        "output_run_dir": str(output_run_dir),
        "primary_family": primary_family,
        "requested_objective": requested_objective,
        "objective_fallback_note": objective_fallback_note,
        "best_params": best_params,
        "backtest_metrics": backtest_metrics,
        "holdout_metrics": holdout_metrics,
        "artifacts": {
            "hotspot_model_pkl": str(model_path),
            "hotspot_feature_list_json": str(feature_list_path),
            "hotspot_training_report_md": str(report_path),
        },
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
