"""Batch scoring entry point for production prediction generation."""

from __future__ import annotations

import argparse
import json
import math
import pickle
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

EPSILON = 1e-9
MISSING_TOKEN = "__MISSING__"
RARE_TOKEN = "__RARE__"


@dataclass(frozen=True)
class RiskThresholds:
    severity_medium: float
    severity_high: float
    combined_medium: float
    combined_high: float
    hotspot_alert_score_threshold: float


def parse_args() -> argparse.Namespace:
    root_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Generate severity, hotspot, and combined risk predictions."
    )
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        default=root_dir / "artifacts" / "snapshots",
        help="Root directory containing extracted snapshot parquet files.",
    )
    parser.add_argument(
        "--feature-root",
        type=Path,
        default=root_dir / "artifacts" / "features",
        help="Root directory containing feature dictionaries used for inference transforms.",
    )
    parser.add_argument(
        "--severity-model-root",
        type=Path,
        default=root_dir / "artifacts" / "models" / "severity",
        help="Root directory containing severity model artifacts.",
    )
    parser.add_argument(
        "--hotspot-model-root",
        type=Path,
        default=root_dir / "artifacts" / "models" / "hotspot",
        help="Root directory containing hotspot model artifacts.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=root_dir / "artifacts" / "predictions",
        help="Root directory for scored prediction outputs.",
    )
    parser.add_argument(
        "--threshold-config",
        type=Path,
        default=root_dir / "configs" / "thresholds.yaml",
        help="Threshold configuration YAML used for risk tiering.",
    )
    parser.add_argument(
        "--hotspot-config",
        type=Path,
        default=root_dir / "configs" / "hotspot.yaml",
        help="Hotspot model config used for default forecast horizon.",
    )
    parser.add_argument(
        "--snapshot-version",
        type=str,
        default="v1",
        help="Snapshot/model version namespace (e.g. v1).",
    )
    parser.add_argument(
        "--snapshot-extraction-date",
        type=str,
        default=None,
        help="Snapshot extraction date (YYYY-MM-DD). If omitted, latest available snapshot is used.",
    )
    parser.add_argument(
        "--severity-model-extraction-date",
        type=str,
        default=None,
        help="Severity model extraction date (YYYY-MM-DD). If omitted, latest available model run is used.",
    )
    parser.add_argument(
        "--hotspot-model-extraction-date",
        type=str,
        default=None,
        help="Hotspot model extraction date (YYYY-MM-DD). If omitted, latest available model run is used.",
    )
    parser.add_argument(
        "--horizons-hours",
        nargs="+",
        type=int,
        default=None,
        help="Forecast horizons (hours ahead). Defaults to 1..forecast_horizon_hours in hotspot config.",
    )
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


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}, got {type(payload).__name__}.")
    return payload


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML mapping at {path}, got {type(payload).__name__}.")
    return payload


def load_pickle(path: Path) -> Any:
    with path.open("rb") as file:
        return pickle.load(file)


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_category_value(value: Any) -> str:
    if pd.isna(value):
        return MISSING_TOKEN
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if pd.isna(value):
            return MISSING_TOKEN
        if float(value).is_integer():
            return f"NUM_{int(value)}"
        return f"NUM_{float(value):.4f}"
    as_text = str(value).strip().upper()
    if not as_text:
        return MISSING_TOKEN
    return as_text


def apply_feature_dictionary(
    frame: pd.DataFrame,
    feature_dictionary: dict[str, Any],
) -> pd.DataFrame:
    numeric_columns = [str(value) for value in feature_dictionary.get("numeric_columns", [])]
    categorical_columns = [str(value) for value in feature_dictionary.get("categorical_columns", [])]
    numeric_imputations = feature_dictionary.get("numeric_imputations", {})
    categorical_keep_values = feature_dictionary.get("categorical_keep_values", {})
    categorical_levels = feature_dictionary.get("categorical_levels", {})
    encoded_feature_names = [str(value) for value in feature_dictionary.get("encoded_feature_names", [])]

    numeric_matrix = pd.DataFrame(index=frame.index)
    for column in numeric_columns:
        source = frame[column] if column in frame.columns else pd.Series(np.nan, index=frame.index)
        numeric_matrix[column] = pd.to_numeric(source, errors="coerce").fillna(
            _safe_float(numeric_imputations.get(column), default=0.0)
        )

    categorical_matrix = pd.DataFrame(index=frame.index)
    for column in categorical_columns:
        source = frame[column] if column in frame.columns else pd.Series(np.nan, index=frame.index)
        raw = source.map(_normalize_category_value)
        keep_values = set(categorical_keep_values.get(column, []))
        bucketed = raw.where(raw.isin(keep_values), RARE_TOKEN)
        levels = [str(value) for value in categorical_levels.get(column, [MISSING_TOKEN, RARE_TOKEN])]
        categorical_matrix[column] = pd.Categorical(bucketed, categories=levels)

    if categorical_columns:
        encoded_categorical = pd.get_dummies(
            categorical_matrix,
            columns=categorical_columns,
            prefix_sep="=",
            dtype="int8",
        )
    else:
        encoded_categorical = pd.DataFrame(index=frame.index)

    transformed = pd.concat([numeric_matrix, encoded_categorical], axis=1)
    if encoded_feature_names:
        transformed = transformed.reindex(columns=encoded_feature_names, fill_value=0)
    return transformed


def clip_probs(values: np.ndarray | pd.Series) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = np.where(np.isfinite(arr), arr, 0.5)
    return np.clip(arr, EPSILON, 1.0 - EPSILON)


def clip_counts(values: np.ndarray | pd.Series) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = np.where(np.isfinite(arr), arr, np.nan)
    finite = arr[np.isfinite(arr)]
    fallback = float(np.mean(finite)) if len(finite) else 1.0
    arr = np.where(np.isfinite(arr), arr, fallback)
    return np.clip(arr, EPSILON, None)


def apply_severity_calibrator(calibrator_bundle: dict[str, Any], raw_scores: np.ndarray) -> np.ndarray:
    method = str(calibrator_bundle.get("method", "")).lower()
    model = calibrator_bundle.get("model")
    if method == "isotonic":
        probs = model.predict(raw_scores)
    elif method == "platt":
        probs = model.predict_proba(raw_scores.reshape(-1, 1))[:, 1]
    else:
        raise ValueError(f"Unsupported calibration method in calibrator bundle: {method!r}")
    return clip_probs(np.asarray(probs, dtype=float))


def derive_grid_id_from_coordinates(latitude: pd.Series, longitude: pd.Series) -> pd.Series:
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
    return pd.Series(values, index=latitude.index)


def nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + (n - 1) * 7)


def last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        last = date(year, 12, 31)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset)


def build_holiday_lookup(years: list[int]) -> set[date]:
    holidays: set[date] = set()
    for year in years:
        holidays.add(date(year, 1, 1))
        holidays.add(date(year, 6, 19))
        holidays.add(date(year, 7, 4))
        holidays.add(date(year, 11, 11))
        holidays.add(date(year, 12, 25))
        holidays.add(nth_weekday_of_month(year, month=1, weekday=0, n=3))  # MLK Day
        holidays.add(nth_weekday_of_month(year, month=2, weekday=0, n=3))  # Presidents' Day
        holidays.add(last_weekday_of_month(year, month=5, weekday=0))  # Memorial Day
        holidays.add(nth_weekday_of_month(year, month=9, weekday=0, n=1))  # Labor Day
        holidays.add(nth_weekday_of_month(year, month=10, weekday=0, n=2))  # Columbus Day
        holidays.add(nth_weekday_of_month(year, month=11, weekday=3, n=4))  # Thanksgiving
    return holidays


def compute_is_holiday(timestamps: pd.Series) -> pd.Series:
    dates = pd.to_datetime(timestamps, errors="coerce").dt.date
    years = sorted({value.year for value in dates.dropna()})
    lookup = build_holiday_lookup(years) if years else set()
    return dates.isin(lookup)


def parse_horizons(args: argparse.Namespace, hotspot_config: dict[str, Any]) -> list[int]:
    if args.horizons_hours:
        horizons = sorted(set(int(value) for value in args.horizons_hours if int(value) > 0))
        if not horizons:
            raise ValueError("--horizons-hours must include at least one positive integer.")
        return horizons
    max_horizon = int(hotspot_config.get("forecast_horizon_hours", 24))
    max_horizon = max(max_horizon, 1)
    return list(range(1, max_horizon + 1))


def load_thresholds(thresholds_config: dict[str, Any]) -> RiskThresholds:
    severity_cfg = thresholds_config.get("severity", {}) if isinstance(thresholds_config, dict) else {}
    combined_cfg = thresholds_config.get("combined", {}) if isinstance(thresholds_config, dict) else {}
    hotspot_cfg = thresholds_config.get("hotspot", {}) if isinstance(thresholds_config, dict) else {}

    severity_high = _safe_float(severity_cfg.get("high_risk_probability"), default=0.65)
    severity_medium = _safe_float(severity_cfg.get("medium_risk_probability"), default=0.40)
    if severity_high < severity_medium:
        severity_high, severity_medium = severity_medium, severity_high

    combined_high = _safe_float(
        combined_cfg.get("high_expected_severe_harm"),
        default=severity_high,
    )
    combined_medium = _safe_float(
        combined_cfg.get("medium_expected_severe_harm"),
        default=severity_medium,
    )
    if combined_high < combined_medium:
        combined_high, combined_medium = combined_medium, combined_high

    hotspot_alert = _safe_float(hotspot_cfg.get("alert_score_threshold"), default=0.70)
    return RiskThresholds(
        severity_medium=severity_medium,
        severity_high=severity_high,
        combined_medium=combined_medium,
        combined_high=combined_high,
        hotspot_alert_score_threshold=hotspot_alert,
    )


def assign_risk_tier(scores: pd.Series, medium: float, high: float) -> pd.Series:
    values = np.asarray(scores, dtype=float)
    tier = np.full(len(values), "low", dtype=object)
    tier[values >= medium] = "medium"
    tier[values >= high] = "high"
    return pd.Series(tier, index=scores.index)


def resolve_model_version(run_dir: Path) -> str:
    version = run_dir.parent.name.split("=", maxsplit=1)[-1]
    extraction = run_dir.name.split("=", maxsplit=1)[-1]
    return f"{version}:{extraction}"


def score_severity(
    *,
    crash_snapshot: pd.DataFrame,
    feature_dictionary: dict[str, Any],
    severity_bundle: dict[str, Any],
    calibrator_bundle: dict[str, Any],
    thresholds: RiskThresholds,
    score_ts_utc: str,
    severity_model_version: str,
    snapshot_version: str,
    snapshot_extraction_date: str,
) -> pd.DataFrame:
    transformed = apply_feature_dictionary(crash_snapshot, feature_dictionary)
    feature_names = list(severity_bundle.get("feature_names", list(transformed.columns)))
    aligned = transformed.reindex(columns=feature_names, fill_value=0)

    model = severity_bundle.get("model")
    if model is None:
        raise ValueError("Severity model bundle is missing required key 'model'.")
    if not hasattr(model, "predict_proba"):
        raise ValueError(f"Severity model type {type(model).__name__} does not implement predict_proba.")

    raw_prob = np.asarray(model.predict_proba(aligned)[:, 1], dtype=float)
    severity_probability = apply_severity_calibrator(calibrator_bundle, raw_prob)

    time_column = str(feature_dictionary.get("time_column", "crash_date"))
    crash_time = pd.to_datetime(crash_snapshot.get(time_column), errors="coerce").dt.floor("h")
    if crash_time.isna().any():
        bad = int(crash_time.isna().sum())
        raise ValueError(f"Severity snapshot has {bad} unparsable timestamps in '{time_column}'.")

    grid_id = derive_grid_id_from_coordinates(
        latitude=crash_snapshot.get("latitude", pd.Series(np.nan, index=crash_snapshot.index)),
        longitude=crash_snapshot.get("longitude", pd.Series(np.nan, index=crash_snapshot.index)),
    )
    output = pd.DataFrame(
        {
            "crash_record_id": crash_snapshot.get("crash_record_id", pd.Series("", index=crash_snapshot.index)).astype(str),
            "crash_date": pd.to_datetime(crash_snapshot.get(time_column), errors="coerce"),
            "time_bucket": crash_time,
            "grid_id": grid_id.astype(str),
            "severity_probability": clip_probs(severity_probability),
        }
    )
    output["risk_tier"] = assign_risk_tier(
        output["severity_probability"],
        medium=thresholds.severity_medium,
        high=thresholds.severity_high,
    )
    output["score_ts_utc"] = score_ts_utc
    output["severity_model_version"] = severity_model_version
    output["snapshot_version"] = snapshot_version
    output["snapshot_extraction_date"] = snapshot_extraction_date
    return output


def build_hotspot_forecast_context(
    hotspot_snapshot: pd.DataFrame,
    *,
    grid_column: str,
    time_column: str,
    horizons_hours: list[int],
) -> pd.DataFrame:
    if grid_column not in hotspot_snapshot.columns:
        raise ValueError(f"Hotspot snapshot is missing grid column '{grid_column}'.")
    if time_column not in hotspot_snapshot.columns:
        raise ValueError(f"Hotspot snapshot is missing time column '{time_column}'.")

    frame = hotspot_snapshot.copy()
    frame[time_column] = pd.to_datetime(frame[time_column], errors="coerce")
    frame = frame[frame[time_column].notna()].copy()
    if frame.empty:
        raise ValueError("Hotspot snapshot has no rows with valid timestamps.")

    context = frame.sort_values([grid_column, time_column]).groupby(grid_column, as_index=False).tail(1).copy()
    pieces: list[pd.DataFrame] = []
    for horizon in horizons_hours:
        part = context.copy()
        part["horizon_hours"] = int(horizon)
        part["forecast_anchor_time"] = part[time_column]
        part["forecast_time"] = part[time_column] + pd.to_timedelta(horizon, unit="h")
        part["day_of_week"] = part["forecast_time"].dt.isocalendar().day.astype(int)
        part["is_weekend"] = part["day_of_week"] >= 6
        part["is_holiday"] = compute_is_holiday(part["forecast_time"])
        pieces.append(part)
    return pd.concat(pieces, axis=0, ignore_index=True)


def score_hotspot(
    *,
    hotspot_snapshot: pd.DataFrame,
    feature_dictionary: dict[str, Any],
    hotspot_bundle: dict[str, Any],
    thresholds: RiskThresholds,
    horizons_hours: list[int],
    score_ts_utc: str,
    hotspot_model_version: str,
    snapshot_version: str,
    snapshot_extraction_date: str,
) -> pd.DataFrame:
    grid_column = str(hotspot_bundle.get("grid_column", feature_dictionary.get("id_columns", ["grid_id"])[0]))
    time_column = str(hotspot_bundle.get("time_column", feature_dictionary.get("time_column", "time_bucket")))
    context = build_hotspot_forecast_context(
        hotspot_snapshot,
        grid_column=grid_column,
        time_column=time_column,
        horizons_hours=horizons_hours,
    )
    transformed = apply_feature_dictionary(context, feature_dictionary)
    feature_names = list(hotspot_bundle.get("feature_names", list(transformed.columns)))
    aligned = transformed.reindex(columns=feature_names, fill_value=0)

    model = hotspot_bundle.get("primary_model")
    if model is None:
        raise ValueError("Hotspot model bundle is missing required key 'primary_model'.")
    predicted_count = clip_counts(np.asarray(model.predict(aligned), dtype=float))

    output = pd.DataFrame(
        {
            "grid_id": context[grid_column].astype(str).to_numpy(),
            "forecast_anchor_time": pd.to_datetime(context["forecast_anchor_time"], errors="coerce").to_numpy(),
            "forecast_time": pd.to_datetime(context["forecast_time"], errors="coerce").to_numpy(),
            "horizon_hours": context["horizon_hours"].astype(int).to_numpy(),
            "predicted_crash_count": predicted_count,
        }
    )
    output["hotspot_alert_score"] = (
        output.groupby("horizon_hours")["predicted_crash_count"]
        .transform(lambda col: col / max(float(col.max()), EPSILON))
        .astype(float)
    )
    output["is_hotspot_alert"] = output["hotspot_alert_score"] >= thresholds.hotspot_alert_score_threshold
    output["score_ts_utc"] = score_ts_utc
    output["hotspot_model_version"] = hotspot_model_version
    output["snapshot_version"] = snapshot_version
    output["snapshot_extraction_date"] = snapshot_extraction_date
    output["version_metadata"] = json.dumps(
        {
            "resolved_primary_family": hotspot_bundle.get("resolved_primary_family"),
            "requested_objective": hotspot_bundle.get("requested_objective"),
            "trained_at_utc": hotspot_bundle.get("trained_at_utc"),
        },
        ensure_ascii=True,
        sort_keys=True,
    )
    return output


def build_combined_rankings(
    *,
    severity_predictions: pd.DataFrame,
    hotspot_forecasts: pd.DataFrame,
    thresholds: RiskThresholds,
    score_ts_utc: str,
    severity_model_version: str,
    hotspot_model_version: str,
    snapshot_version: str,
    snapshot_extraction_date: str,
) -> pd.DataFrame:
    sev = severity_predictions.copy()
    sev["hour_of_day"] = pd.to_datetime(sev["time_bucket"], errors="coerce").dt.hour
    sev_grid_hour = sev.groupby(["grid_id", "hour_of_day"], as_index=False)["severity_probability"].mean()
    sev_grid_hour.rename(columns={"severity_probability": "severity_prob_grid_hour"}, inplace=True)

    sev_grid = sev.groupby("grid_id", as_index=False)["severity_probability"].mean()
    sev_grid.rename(columns={"severity_probability": "severity_prob_grid"}, inplace=True)

    global_severity_prob = float(sev["severity_probability"].mean()) if len(sev) else 0.0

    combined = hotspot_forecasts.copy()
    combined["hour_of_day"] = pd.to_datetime(combined["forecast_time"], errors="coerce").dt.hour
    combined = combined.merge(sev_grid_hour, on=["grid_id", "hour_of_day"], how="left")
    combined = combined.merge(sev_grid, on="grid_id", how="left")
    combined["severity_probability"] = combined["severity_prob_grid_hour"].fillna(combined["severity_prob_grid"])
    combined["severity_probability"] = combined["severity_probability"].fillna(global_severity_prob)
    combined["expected_severe_harm"] = (
        combined["predicted_crash_count"].astype(float) * combined["severity_probability"].astype(float)
    )
    combined["risk_tier"] = assign_risk_tier(
        combined["expected_severe_harm"],
        medium=thresholds.combined_medium,
        high=thresholds.combined_high,
    )
    combined["risk_rank"] = (
        combined["expected_severe_harm"].rank(method="dense", ascending=False).astype("int64")
    )
    combined["score_ts_utc"] = score_ts_utc
    combined["severity_model_version"] = severity_model_version
    combined["hotspot_model_version"] = hotspot_model_version
    combined["snapshot_version"] = snapshot_version
    combined["snapshot_extraction_date"] = snapshot_extraction_date
    return combined[
        [
            "grid_id",
            "forecast_time",
            "horizon_hours",
            "expected_severe_harm",
            "risk_rank",
            "risk_tier",
            "severity_probability",
            "predicted_crash_count",
            "score_ts_utc",
            "severity_model_version",
            "hotspot_model_version",
            "snapshot_version",
            "snapshot_extraction_date",
        ]
    ].copy()


def main() -> None:
    args = parse_args()
    score_ts_utc = datetime.now(timezone.utc).isoformat()

    snapshot_run_dir = resolve_run_dir(
        base_root=args.snapshot_root,
        version=args.snapshot_version,
        extraction_date=args.snapshot_extraction_date,
    )
    snapshot_extraction_date = snapshot_run_dir.name.split("=", maxsplit=1)[-1]

    severity_model_run_dir = resolve_run_dir(
        base_root=args.severity_model_root,
        version=args.snapshot_version,
        extraction_date=args.severity_model_extraction_date,
    )
    hotspot_model_run_dir = resolve_run_dir(
        base_root=args.hotspot_model_root,
        version=args.snapshot_version,
        extraction_date=args.hotspot_model_extraction_date,
    )
    severity_feature_run_dir = resolve_run_dir(
        base_root=args.feature_root,
        version=args.snapshot_version,
        extraction_date=severity_model_run_dir.name.split("=", maxsplit=1)[-1],
    )
    hotspot_feature_run_dir = resolve_run_dir(
        base_root=args.feature_root,
        version=args.snapshot_version,
        extraction_date=hotspot_model_run_dir.name.split("=", maxsplit=1)[-1],
    )

    thresholds_cfg = load_yaml(args.threshold_config)
    hotspot_cfg = load_yaml(args.hotspot_config)
    thresholds = load_thresholds(thresholds_cfg)
    horizons_hours = parse_horizons(args=args, hotspot_config=hotspot_cfg)

    crash_snapshot_path = snapshot_run_dir / "ml_crash_base_v1.parquet"
    hotspot_snapshot_path = snapshot_run_dir / "ml_hotspot_ts_v1.parquet"
    severity_dictionary_path = severity_feature_run_dir / "severity" / "feature_dictionary.json"
    hotspot_dictionary_path = hotspot_feature_run_dir / "hotspot" / "feature_dictionary.json"
    severity_model_path = severity_model_run_dir / "severity_model.pkl"
    severity_calibrator_path = severity_model_run_dir / "severity_calibrator.pkl"
    hotspot_model_path = hotspot_model_run_dir / "hotspot_model.pkl"

    for path in (
        crash_snapshot_path,
        hotspot_snapshot_path,
        severity_dictionary_path,
        hotspot_dictionary_path,
        severity_model_path,
        severity_calibrator_path,
        hotspot_model_path,
    ):
        if not path.exists():
            raise FileNotFoundError(f"Required scoring artifact not found: {path}")

    crash_snapshot = pd.read_parquet(crash_snapshot_path)
    hotspot_snapshot = pd.read_parquet(hotspot_snapshot_path)
    severity_dictionary = load_json(severity_dictionary_path)
    hotspot_dictionary = load_json(hotspot_dictionary_path)
    severity_bundle = load_pickle(severity_model_path)
    severity_calibrator = load_pickle(severity_calibrator_path)
    hotspot_bundle = load_pickle(hotspot_model_path)

    severity_model_version = resolve_model_version(severity_model_run_dir)
    hotspot_model_version = resolve_model_version(hotspot_model_run_dir)

    severity_predictions = score_severity(
        crash_snapshot=crash_snapshot,
        feature_dictionary=severity_dictionary,
        severity_bundle=severity_bundle,
        calibrator_bundle=severity_calibrator,
        thresholds=thresholds,
        score_ts_utc=score_ts_utc,
        severity_model_version=severity_model_version,
        snapshot_version=args.snapshot_version,
        snapshot_extraction_date=snapshot_extraction_date,
    )
    hotspot_forecasts = score_hotspot(
        hotspot_snapshot=hotspot_snapshot,
        feature_dictionary=hotspot_dictionary,
        hotspot_bundle=hotspot_bundle,
        thresholds=thresholds,
        horizons_hours=horizons_hours,
        score_ts_utc=score_ts_utc,
        hotspot_model_version=hotspot_model_version,
        snapshot_version=args.snapshot_version,
        snapshot_extraction_date=snapshot_extraction_date,
    )
    combined_rankings = build_combined_rankings(
        severity_predictions=severity_predictions,
        hotspot_forecasts=hotspot_forecasts,
        thresholds=thresholds,
        score_ts_utc=score_ts_utc,
        severity_model_version=severity_model_version,
        hotspot_model_version=hotspot_model_version,
        snapshot_version=args.snapshot_version,
        snapshot_extraction_date=snapshot_extraction_date,
    )

    output_run_dir = (
        args.output_root
        / f"version={args.snapshot_version}"
        / f"extraction_date={snapshot_extraction_date}"
    )
    output_run_dir.mkdir(parents=True, exist_ok=True)

    severity_path = output_run_dir / "ml_severity_predictions.parquet"
    hotspot_path = output_run_dir / "ml_hotspot_forecasts.parquet"
    combined_path = output_run_dir / "ml_combined_risk_rankings.parquet"
    manifest_path = output_run_dir / "manifest.json"

    severity_predictions.to_parquet(severity_path, index=False)
    hotspot_forecasts.to_parquet(hotspot_path, index=False)
    combined_rankings.to_parquet(combined_path, index=False)

    manifest = {
        "generated_at_utc": score_ts_utc,
        "snapshot_version": args.snapshot_version,
        "snapshot_extraction_date": snapshot_extraction_date,
        "snapshot_run_dir": str(snapshot_run_dir),
        "severity_model_run_dir": str(severity_model_run_dir),
        "hotspot_model_run_dir": str(hotspot_model_run_dir),
        "severity_feature_run_dir": str(severity_feature_run_dir),
        "hotspot_feature_run_dir": str(hotspot_feature_run_dir),
        "horizons_hours": horizons_hours,
        "thresholds": {
            "severity_medium": thresholds.severity_medium,
            "severity_high": thresholds.severity_high,
            "combined_medium": thresholds.combined_medium,
            "combined_high": thresholds.combined_high,
            "hotspot_alert_score_threshold": thresholds.hotspot_alert_score_threshold,
        },
        "row_counts": {
            "ml_severity_predictions": int(len(severity_predictions)),
            "ml_hotspot_forecasts": int(len(hotspot_forecasts)),
            "ml_combined_risk_rankings": int(len(combined_rankings)),
        },
        "outputs": {
            "ml_severity_predictions": str(severity_path),
            "ml_hotspot_forecasts": str(hotspot_path),
            "ml_combined_risk_rankings": str(combined_path),
        },
    }
    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=True, indent=2, sort_keys=True)
    manifest["manifest_path"] = str(manifest_path)
    print(json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
