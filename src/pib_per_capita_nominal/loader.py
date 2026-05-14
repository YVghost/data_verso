"""
ETL loader: PIB Per Capita Nominal — BCE Ecuador

Tabla: pib_per_capita_nominal
Esquema:
  id                   BIGINT IDENTITY PK
  anio                 INT     NOT NULL
  pib_per_capita_usd   FLOAT   NOT NULL   -- USD corrientes per capita
  fecha_actualizacion  DATE    NULL       -- ultima carga en BCE
  hash_registro        NVARCHAR(64) NOT NULL
  fecha_carga          DATETIME2 DEFAULT GETDATE()

Deduplicacion: hash sobre (anio, pib_per_capita_usd).
"""

import hashlib
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.base_engine import get_master_engine

_TABLE = "pib_per_capita_nominal"

_DDL = """
CREATE TABLE pib_per_capita_nominal (
    id                   BIGINT IDENTITY(1,1) NOT NULL,
    anio                 INT           NOT NULL,
    pib_per_capita_usd   FLOAT         NOT NULL,
    fecha_actualizacion  DATE          NULL,
    hash_registro        NVARCHAR(64)  NOT NULL,
    fecha_carga          DATETIME2     DEFAULT GETDATE(),
    CONSTRAINT PK_pib_per_capita_nominal PRIMARY KEY NONCLUSTERED (id)
)"""

_IDX = "CREATE CLUSTERED INDEX CIX_pib_per_capita_nominal ON pib_per_capita_nominal (anio)"


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def load(records: list[dict]) -> None:
    if not records:
        print("[pib_pc] Sin datos para cargar.")
        return

    for rec in records:
        rec["hash_registro"] = _hash(rec)

    engine = get_master_engine()
    _ensure_table(engine)
    _upsert(records, engine)


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

def _ensure_table(engine) -> None:
    from sqlalchemy import inspect as sa_inspect
    if not sa_inspect(engine).has_table(_TABLE):
        with engine.begin() as conn:
            conn.execute(text(_DDL))
            conn.execute(text(_IDX))
        print(f"[pib_pc] Tabla {_TABLE} creada.")


# ---------------------------------------------------------------------------
# Insercion con deduplicacion
# ---------------------------------------------------------------------------

def _upsert(records: list[dict], engine) -> None:
    with engine.connect() as conn:
        existing = {row[0] for row in conn.execute(
            text(f"SELECT hash_registro FROM {_TABLE}")
        )}

    new = [r for r in records if r["hash_registro"] not in existing]
    if not new:
        print(f"[pib_pc] Sin registros nuevos (todos ya existen en BD).")
        return

    cols         = list(new[0].keys())
    col_list     = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    with engine.begin() as conn:
        conn.execute(text(f"INSERT INTO {_TABLE} ({col_list}) VALUES ({placeholders})"), new)

    print(f"[pib_pc] {len(new)} nuevos registros insertados en {_TABLE}.")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _hash(rec: dict) -> str:
    key = f"{rec['anio']}|{rec['pib_per_capita_usd']}"
    return hashlib.sha256(key.encode()).hexdigest()
