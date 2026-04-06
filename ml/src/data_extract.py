"""Extract curated ML tables from Postgres and persist versioned snapshots."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine

DEFAULT_TABLES = ("ml_crash_base_v1", "ml_hotspot_ts_v1")
VALID_IDENTIFIER_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


@dataclass(frozen=True)
class ExtractConfig:
    database_url: str
    snapshot_version: str
    extraction_date: str
    output_root: Path
    schema: str | None
    tables: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    root_dir = Path(__file__).resolve().parents[1]
    default_output_root = root_dir / "artifacts" / "snapshots"

    parser = argparse.ArgumentParser(
        description="Extract curated ML tables from Postgres into parquet snapshots."
    )
    parser.add_argument("--database-url", type=str, default=os.getenv("DATABASE_URL"))
    parser.add_argument("--db-user", type=str, default=os.getenv("DB_USER", "user"))
    parser.add_argument("--db-pass", type=str, default=os.getenv("DB_PASS", "password"))
    parser.add_argument("--db-host", type=str, default=os.getenv("DB_HOST", "localhost"))
    parser.add_argument("--db-port", type=str, default=os.getenv("DB_PORT", "5432"))
    parser.add_argument("--db-name", type=str, default=os.getenv("DB_NAME", "traffic_crashes"))
    parser.add_argument(
        "--db-driver",
        type=str,
        default=os.getenv("DB_DRIVER", "postgresql+psycopg2"),
        help="SQLAlchemy driver prefix, e.g. postgresql+psycopg2",
    )
    parser.add_argument(
        "--snapshot-version",
        type=str,
        default="v1",
        help="Version tag embedded in snapshot output path.",
    )
    parser.add_argument(
        "--extraction-date",
        type=str,
        default=datetime.now(timezone.utc).date().isoformat(),
        help="Extraction date (YYYY-MM-DD) embedded in snapshot output path.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=default_output_root,
        help="Base output directory for snapshot artifacts.",
    )
    parser.add_argument(
        "--schema",
        type=str,
        default=None,
        help="Optional DB schema. If omitted, default schema search path is used.",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        default=list(DEFAULT_TABLES),
        help="Tables to extract.",
    )
    return parser.parse_args()


def _is_valid_identifier(value: str) -> bool:
    return bool(value) and all(char in VALID_IDENTIFIER_CHARS for char in value)


def _qualify_table(schema: str | None, table: str) -> str:
    if not _is_valid_identifier(table):
        raise ValueError(f"Invalid table identifier: {table!r}")
    if schema is None:
        return table
    if not _is_valid_identifier(schema):
        raise ValueError(f"Invalid schema identifier: {schema!r}")
    return f"{schema}.{table}"


def build_database_url(args: argparse.Namespace) -> str:
    if args.database_url:
        return args.database_url
    return (
        f"{args.db_driver}://{args.db_user}:{args.db_pass}"
        f"@{args.db_host}:{args.db_port}/{args.db_name}"
    )


def _to_extract_config(args: argparse.Namespace) -> ExtractConfig:
    return ExtractConfig(
        database_url=build_database_url(args),
        snapshot_version=args.snapshot_version,
        extraction_date=args.extraction_date,
        output_root=args.output_root,
        schema=args.schema,
        tables=tuple(args.tables),
    )


def _extract_table(engine: Any, schema: str | None, table: str) -> pd.DataFrame:
    qualified_table = _qualify_table(schema=schema, table=table)
    query = f"SELECT * FROM {qualified_table}"
    return pd.read_sql_query(query, con=engine)


def run_extract(config: ExtractConfig) -> dict[str, Any]:
    extraction_ts = datetime.now(timezone.utc).isoformat()
    run_dir = (
        config.output_root
        / f"version={config.snapshot_version}"
        / f"extraction_date={config.extraction_date}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "snapshot_version": config.snapshot_version,
        "extraction_date": config.extraction_date,
        "extracted_at_utc": extraction_ts,
        "tables": {},
    }

    engine = create_engine(config.database_url, future=True)
    try:
        for table_name in config.tables:
            frame = _extract_table(engine=engine, schema=config.schema, table=table_name)
            output_path = run_dir / f"{table_name}.parquet"
            frame.to_parquet(output_path, index=False)
            manifest["tables"][table_name] = {
                "row_count": int(len(frame)),
                "column_count": int(frame.shape[1]),
                "columns": list(frame.columns),
                "dtypes": {column: str(dtype) for column, dtype in frame.dtypes.items()},
                "path": str(output_path),
            }
    finally:
        engine.dispose()

    manifest_path = run_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=True, indent=2, sort_keys=True)

    manifest["manifest_path"] = str(manifest_path)
    return manifest


def main() -> None:
    args = parse_args()
    config = _to_extract_config(args)
    manifest = run_extract(config)
    print(json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
