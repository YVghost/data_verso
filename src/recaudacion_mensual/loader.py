import sys
import pandas as pd
from pathlib import Path
from sqlalchemy import inspect as sa_inspect

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.base_engine import get_master_engine

TABLE_NAME = "recaudacion_mensual"
KEY_COLS = ["anio", "mes", "provincia"]


def load(df: pd.DataFrame) -> None:
    if df.empty:
        print(f"[{TABLE_NAME}] Sin datos para cargar.")
        return
    engine = get_master_engine()
    _ensure_table_exists(engine, df)
    new_rows = _filter_duplicates(df, engine)
    if new_rows.empty:
        print(f"[{TABLE_NAME}] Sin registros nuevos, todos ya existen en BD.")
        return
    new_rows.to_sql(TABLE_NAME, engine, if_exists="append", index=False)
    print(f"[{TABLE_NAME}] {len(new_rows)} filas nuevas cargadas.")


def _ensure_table_exists(engine, df: pd.DataFrame) -> None:
    inspector = sa_inspect(engine)
    if not inspector.has_table(TABLE_NAME):
        df.head(0).to_sql(TABLE_NAME, engine, index=False)
        print(f"[{TABLE_NAME}] Tabla creada.")


def _filter_duplicates(df: pd.DataFrame, engine) -> pd.DataFrame:
    inspector = sa_inspect(engine)
    if not inspector.has_table(TABLE_NAME):
        return df
    with engine.connect() as conn:
        existing = pd.read_sql(
            f"SELECT {', '.join(KEY_COLS)} FROM {TABLE_NAME}", conn
        )
    if existing.empty:
        return df
    merged = df.merge(existing, on=KEY_COLS, how="left", indicator=True)
    return merged[merged["_merge"] == "left_only"].drop(columns=["_merge"]).reset_index(drop=True)
