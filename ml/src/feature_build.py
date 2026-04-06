"""Build transformed feature matrices from extracted parquet snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

MISSING_TOKEN = "__MISSING__"
RARE_TOKEN = "__RARE__"


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    snapshot_file: str
    time_column: str
    target_column: str
    id_columns: tuple[str, ...]
    excluded_feature_columns: tuple[str, ...] = ()


DATASET_SPECS: dict[str, DatasetSpec] = {
    "severity": DatasetSpec(
        name="severity",
        snapshot_file="ml_crash_base_v1.parquet",
        time_column="crash_date",
        target_column="severe_injury_flag",
        id_columns=("crash_record_id",),
        # These directly define or decompose the target and should be excluded.
        excluded_feature_columns=(
            "injuries_fatal",
            "injuries_incapacitating",
            "injuries_others",
            "data_freshness_ts",
        ),
    ),
    "hotspot": DatasetSpec(
        name="hotspot",
        snapshot_file="ml_hotspot_ts_v1.parquet",
        time_column="time_bucket",
        target_column="crash_count",
        id_columns=("grid_id", "time_bucket"),
        excluded_feature_columns=("data_freshness_ts",),
    ),
}


@dataclass(frozen=True)
class PreprocessConfig:
    rare_min_frequency: float
    rare_min_count: int
    max_discrete_levels: int


@dataclass
class FittedPreprocessor:
    numeric_columns: list[str]
    categorical_columns: list[str]
    numeric_imputations: dict[str, float]
    categorical_keep_values: dict[str, set[str]]
    categorical_levels: dict[str, list[str]]
    encoded_feature_names: list[str]


def parse_args() -> argparse.Namespace:
    root_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Build feature matrices using temporal split policy."
    )
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        default=root_dir / "artifacts" / "snapshots",
        help="Base snapshot directory.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=root_dir / "artifacts" / "features",
        help="Base output directory for transformed features.",
    )
    parser.add_argument(
        "--snapshot-version",
        type=str,
        default="v1",
        help="Snapshot version to read, matching data_extract.py output.",
    )
    parser.add_argument(
        "--extraction-date",
        type=str,
        default=None,
        help="Snapshot extraction date (YYYY-MM-DD). If omitted, latest available is used.",
    )
    parser.add_argument(
        "--split-policy",
        type=Path,
        default=root_dir / "configs" / "split_policy.yaml",
        help="Path to temporal split policy config.",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["severity", "hotspot"],
        choices=list(DATASET_SPECS.keys()),
        help="Datasets to transform.",
    )
    parser.add_argument(
        "--rare-min-frequency",
        type=float,
        default=0.01,
        help="Minimum training frequency for a category to avoid rare-class bucketing.",
    )
    parser.add_argument(
        "--rare-min-count",
        type=int,
        default=50,
        help="Minimum absolute training count for a category to avoid rare-class bucketing.",
    )
    parser.add_argument(
        "--max-discrete-levels",
        type=int,
        default=24,
        help="Max unique values for a numeric column to be bucketed as categorical.",
    )
    return parser.parse_args()


def resolve_snapshot_dir(snapshot_root: Path, version: str, extraction_date: str | None) -> Path:
    version_dir = snapshot_root / f"version={version}"
    if not version_dir.exists():
        raise FileNotFoundError(f"Snapshot version directory not found: {version_dir}")

    if extraction_date:
        selected = version_dir / f"extraction_date={extraction_date}"
        if not selected.exists():
            raise FileNotFoundError(f"Snapshot extraction directory not found: {selected}")
        return selected

    candidates = sorted(
        [path for path in version_dir.glob("extraction_date=*") if path.is_dir()],
        key=lambda path: path.name,
    )
    if not candidates:
        raise FileNotFoundError(f"No extraction directories found under: {version_dir}")
    return candidates[-1]


def load_split_policy(policy_path: Path) -> dict[str, Any]:
    with policy_path.open("r", encoding="utf-8") as file:
        policy = yaml.safe_load(file)
    if not isinstance(policy, dict):
        raise ValueError(f"Invalid split policy content in {policy_path}")
    required_fields = {
        "train_start",
        "train_end",
        "validation_start",
        "validation_end",
        "test_start",
        "test_end",
    }
    missing = required_fields - set(policy.keys())
    if missing:
        raise KeyError(f"Split policy missing required keys: {sorted(missing)}")
    return policy


def _safe_float(value: Any, default: float = 0.0) -> float:
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


def _to_categorical_series(series: pd.Series) -> pd.Series:
    return series.map(_normalize_category_value)


def infer_feature_columns(
    frame: pd.DataFrame,
    spec: DatasetSpec,
    max_discrete_levels: int,
) -> tuple[list[str], list[str]]:
    excluded = set(spec.id_columns)
    excluded.add(spec.time_column)
    excluded.add(spec.target_column)
    excluded.update(spec.excluded_feature_columns)

    base_columns = [column for column in frame.columns if column not in excluded]
    numeric_columns: list[str] = []
    categorical_columns: list[str] = []

    for column in base_columns:
        series = frame[column]
        if pd.api.types.is_bool_dtype(series):
            categorical_columns.append(column)
            continue
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            categorical_columns.append(column)
            continue
        if pd.api.types.is_numeric_dtype(series):
            non_null_unique = int(series.dropna().nunique())
            if non_null_unique <= max_discrete_levels:
                categorical_columns.append(column)
            else:
                numeric_columns.append(column)
            continue
        categorical_columns.append(column)

    return sorted(numeric_columns), sorted(categorical_columns)


def split_by_policy(
    frame: pd.DataFrame,
    time_column: str,
    policy: dict[str, Any],
) -> tuple[dict[str, pd.DataFrame], int]:
    frame = frame.copy()
    frame[time_column] = pd.to_datetime(frame[time_column], errors="coerce")
    if frame[time_column].isna().any():
        frame = frame[frame[time_column].notna()].copy()

    dates = frame[time_column].dt.date
    train_start = pd.to_datetime(policy["train_start"]).date()
    train_end = pd.to_datetime(policy["train_end"]).date()
    val_start = pd.to_datetime(policy["validation_start"]).date()
    val_end = pd.to_datetime(policy["validation_end"]).date()
    test_start = pd.to_datetime(policy["test_start"]).date()
    test_end = pd.to_datetime(policy["test_end"]).date()

    train_mask = (dates >= train_start) & (dates <= train_end)
    val_mask = (dates >= val_start) & (dates <= val_end)
    test_mask = (dates >= test_start) & (dates <= test_end)

    train = frame.loc[train_mask].copy()
    validation = frame.loc[val_mask].copy()
    test = frame.loc[test_mask].copy()
    unassigned = int(len(frame) - len(train) - len(validation) - len(test))

    return {"train": train, "validation": validation, "test": test}, unassigned


def fit_preprocessor(
    train_df: pd.DataFrame,
    numeric_columns: list[str],
    categorical_columns: list[str],
    config: PreprocessConfig,
) -> FittedPreprocessor:
    if train_df.empty:
        raise ValueError("Training split is empty; cannot fit preprocessing.")

    numeric_imputations: dict[str, float] = {}
    for column in numeric_columns:
        median = train_df[column].median(skipna=True)
        numeric_imputations[column] = _safe_float(median, default=0.0)

    categorical_keep_values: dict[str, set[str]] = {}
    categorical_levels: dict[str, list[str]] = {}
    for column in categorical_columns:
        cat_series = _to_categorical_series(train_df[column])
        counts = cat_series.value_counts(dropna=False)
        threshold = max(
            config.rare_min_count,
            int(round(config.rare_min_frequency * len(cat_series))),
        )
        keep = {
            value
            for value, count in counts.items()
            if int(count) >= threshold or value == MISSING_TOKEN
        }
        if not keep:
            keep = {MISSING_TOKEN}
        train_bucketed = cat_series.where(cat_series.isin(keep), RARE_TOKEN)
        levels = sorted(set(train_bucketed.tolist()) | {RARE_TOKEN, MISSING_TOKEN})
        if not levels:
            levels = [MISSING_TOKEN]
        categorical_keep_values[column] = keep
        categorical_levels[column] = levels

    fitted = FittedPreprocessor(
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        numeric_imputations=numeric_imputations,
        categorical_keep_values=categorical_keep_values,
        categorical_levels=categorical_levels,
        encoded_feature_names=[],
    )
    return fitted


def transform_features(frame: pd.DataFrame, fitted: FittedPreprocessor) -> pd.DataFrame:
    numeric_matrix = pd.DataFrame(index=frame.index)
    for column in fitted.numeric_columns:
        numeric_matrix[column] = pd.to_numeric(frame[column], errors="coerce").fillna(
            fitted.numeric_imputations[column]
        )

    categorical_matrix = pd.DataFrame(index=frame.index)
    for column in fitted.categorical_columns:
        raw = _to_categorical_series(frame[column])
        keep = fitted.categorical_keep_values[column]
        bucketed = raw.where(raw.isin(keep), RARE_TOKEN)
        levels = fitted.categorical_levels[column]
        categorical_matrix[column] = pd.Categorical(bucketed, categories=levels)

    if fitted.categorical_columns:
        encoded_categorical = pd.get_dummies(
            categorical_matrix,
            columns=fitted.categorical_columns,
            prefix_sep="=",
            dtype="int8",
        )
    else:
        encoded_categorical = pd.DataFrame(index=frame.index)

    transformed = pd.concat([numeric_matrix, encoded_categorical], axis=1)
    return transformed


def schema_hash(frame: pd.DataFrame) -> str:
    schema_repr = [
        {"column": column, "dtype": str(frame[column].dtype)} for column in frame.columns
    ]
    payload = json.dumps(schema_repr, ensure_ascii=True, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def persist_split_outputs(
    dataset_output_dir: Path,
    spec: DatasetSpec,
    split_frames: dict[str, pd.DataFrame],
    split_features: dict[str, pd.DataFrame],
) -> dict[str, int]:
    row_counts: dict[str, int] = {}
    for split_name, split_df in split_frames.items():
        dataset_output_dir.mkdir(parents=True, exist_ok=True)
        x_frame = split_features[split_name].reset_index(drop=True)
        y_frame = split_df[[spec.target_column]].reset_index(drop=True)
        key_columns = list(spec.id_columns)
        key_frame = split_df[key_columns].copy().reset_index(drop=True)
        if spec.time_column not in key_columns:
            key_frame[spec.time_column] = split_df[spec.time_column].reset_index(drop=True)

        x_frame.to_parquet(dataset_output_dir / f"X_{split_name}.parquet", index=False)
        y_frame.to_parquet(dataset_output_dir / f"y_{split_name}.parquet", index=False)
        key_frame.to_parquet(dataset_output_dir / f"keys_{split_name}.parquet", index=False)
        row_counts[split_name] = int(len(split_df))
    return row_counts


def process_dataset(
    spec: DatasetSpec,
    snapshot_dir: Path,
    output_run_dir: Path,
    policy: dict[str, Any],
    preprocess_config: PreprocessConfig,
) -> dict[str, Any]:
    source_path = snapshot_dir / spec.snapshot_file
    if not source_path.exists():
        raise FileNotFoundError(f"Snapshot file not found for {spec.name}: {source_path}")

    frame = pd.read_parquet(source_path)
    source_schema_hash = schema_hash(frame)
    split_frames, unassigned_count = split_by_policy(frame, spec.time_column, policy)

    train_frame = split_frames["train"]
    numeric_columns, categorical_columns = infer_feature_columns(
        frame=train_frame,
        spec=spec,
        max_discrete_levels=preprocess_config.max_discrete_levels,
    )
    fitted = fit_preprocessor(
        train_df=train_frame,
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        config=preprocess_config,
    )

    split_features: dict[str, pd.DataFrame] = {}
    for split_name, split_df in split_frames.items():
        transformed = transform_features(split_df, fitted)
        split_features[split_name] = transformed

    # Freeze feature list from train and reindex all other splits to match.
    fitted.encoded_feature_names = list(split_features["train"].columns)
    for split_name in split_features:
        split_features[split_name] = split_features[split_name].reindex(
            columns=fitted.encoded_feature_names, fill_value=0
        )

    dataset_output_dir = output_run_dir / spec.name
    split_row_counts = persist_split_outputs(
        dataset_output_dir=dataset_output_dir,
        spec=spec,
        split_frames=split_frames,
        split_features=split_features,
    )

    feature_dictionary = {
        "dataset": spec.name,
        "target_column": spec.target_column,
        "time_column": spec.time_column,
        "id_columns": list(spec.id_columns),
        "numeric_columns": fitted.numeric_columns,
        "categorical_columns": fitted.categorical_columns,
        "numeric_imputations": fitted.numeric_imputations,
        "categorical_keep_values": {
            column: sorted(values) for column, values in fitted.categorical_keep_values.items()
        },
        "categorical_levels": fitted.categorical_levels,
        "rare_token": RARE_TOKEN,
        "missing_token": MISSING_TOKEN,
        "encoded_feature_names": fitted.encoded_feature_names,
    }

    metadata = {
        "dataset": spec.name,
        "source_snapshot": str(source_path),
        "schema_hash": source_schema_hash,
        "row_counts": {
            "total_input": int(len(frame)),
            "unassigned": int(unassigned_count),
            **split_row_counts,
        },
        "feature_list": fitted.encoded_feature_names,
        "split_date_boundaries": {
            "train": {"start": policy["train_start"], "end": policy["train_end"]},
            "validation": {
                "start": policy["validation_start"],
                "end": policy["validation_end"],
            },
            "test": {"start": policy["test_start"], "end": policy["test_end"]},
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    dictionary_path = dataset_output_dir / "feature_dictionary.json"
    metadata_path = dataset_output_dir / "metadata.json"
    with dictionary_path.open("w", encoding="utf-8") as file:
        json.dump(feature_dictionary, file, ensure_ascii=True, indent=2, sort_keys=True)
    with metadata_path.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=True, indent=2, sort_keys=True)

    return {
        "dataset": spec.name,
        "output_dir": str(dataset_output_dir),
        "feature_dictionary_path": str(dictionary_path),
        "metadata_path": str(metadata_path),
        "row_counts": metadata["row_counts"],
        "feature_count": len(fitted.encoded_feature_names),
    }


def main() -> None:
    args = parse_args()
    snapshot_dir = resolve_snapshot_dir(
        snapshot_root=args.snapshot_root,
        version=args.snapshot_version,
        extraction_date=args.extraction_date,
    )
    extraction_date = snapshot_dir.name.split("=", maxsplit=1)[-1]
    output_run_dir = (
        args.output_root
        / f"version={args.snapshot_version}"
        / f"extraction_date={extraction_date}"
    )
    output_run_dir.mkdir(parents=True, exist_ok=True)

    policy = load_split_policy(args.split_policy)
    preprocess_config = PreprocessConfig(
        rare_min_frequency=args.rare_min_frequency,
        rare_min_count=args.rare_min_count,
        max_discrete_levels=args.max_discrete_levels,
    )

    results = []
    for dataset_name in args.datasets:
        spec = DATASET_SPECS[dataset_name]
        result = process_dataset(
            spec=spec,
            snapshot_dir=snapshot_dir,
            output_run_dir=output_run_dir,
            policy=policy,
            preprocess_config=preprocess_config,
        )
        results.append(result)

    run_manifest = {
        "snapshot_version": args.snapshot_version,
        "extraction_date": extraction_date,
        "snapshot_dir": str(snapshot_dir),
        "output_run_dir": str(output_run_dir),
        "split_policy_path": str(args.split_policy),
        "split_policy_name": policy.get("policy_name"),
        "datasets": results,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = output_run_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(run_manifest, file, ensure_ascii=True, indent=2, sort_keys=True)

    print(json.dumps(run_manifest, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
