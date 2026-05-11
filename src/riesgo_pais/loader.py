"""
ETL loader: Riesgo Pais (EMBI) — BCE Ecuador

Tabla: riesgo_pais
Esquema:
  id                    BIGINT IDENTITY PK
  fecha                 DATE     NOT NULL   -- fecha del dato diario
  valor_riesgo_pais     FLOAT    NOT NULL   -- EMBI en puntos basicos
  fecha_actualizacion   DATE     NULL       -- fecha de carga en BCE ("Carga")
  hash_registro         NVARCHAR(64) NOT NULL
  fecha_carga           DATETIME2 DEFAULT GETDATE()

Deduplicacion: hash sobre (fecha, valor_riesgo_pais).
"""

import hashlib
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.base_engine import get_master_engine

_TABLE = "riesgo_pais"

_DDL = """
CREATE TABLE riesgo_pais (
    id                   BIGINT IDENTITY(1,1) NOT NULL,
    fecha                DATE          NOT NULL,
    valor_riesgo_pais    FLOAT         NOT NULL,
    fecha_actualizacion  DATE          NULL,
    hash_registro        NVARCHAR(64)  NOT NULL,
    fecha_carga          DATETIME2     DEFAULT GETDATE(),
    CONSTRAINT PK_riesgo_pais PRIMARY KEY NONCLUSTERED (id)
)"""

_IDX = """
CREATE CLUSTERED INDEX CIX_riesgo_pais
ON riesgo_pais (fecha)"""


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def load(records: list[dict]) -> None:
    """
    Recibe lista de dicts con keys: fecha, valor_riesgo_pais, fecha_actualizacion.
    Agrega hash_registro y sube solo registros nuevos.
    """
    if not records:
        print(f"[rp] Sin datos para cargar.")
        return

    # Enriquecer con hash
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
    insp = sa_inspect(engine)
    if insp.has_table(_TABLE):
        cols = {c["name"] for c in insp.get_columns(_TABLE)}
        if "valor_riesgo_pais" not in cols:
            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE {_TABLE}"))
            print(f"[rp] Tabla {_TABLE} eliminada (esquema desactualizado).")
            insp = sa_inspect(engine)
    if not insp.has_table(_TABLE):
        with engine.begin() as conn:
            conn.execute(text(_DDL))
            conn.execute(text(_IDX))
        print(f"[rp] Tabla {_TABLE} creada.")


# ---------------------------------------------------------------------------
# Insercion con deduplicacion por hash
# ---------------------------------------------------------------------------

def _upsert(records: list[dict], engine) -> None:
    with engine.connect() as conn:
        result   = conn.execute(text(f"SELECT hash_registro FROM {_TABLE}"))
        existing = {row[0] for row in result}

    new = [r for r in records if r["hash_registro"] not in existing]
    if not new:
        print(f"[rp] Sin registros nuevos (todos ya existen en BD).")
        return

    cols         = list(new[0].keys())
    col_list     = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    sql          = text(f"INSERT INTO {_TABLE} ({col_list}) VALUES ({placeholders})")

    with engine.begin() as conn:
        conn.execute(sql, new)

    print(f"[rp] {len(new)} nuevos registros insertados en {_TABLE}.")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _hash(rec: dict) -> str:
    key = f"{rec['fecha']}|{rec['valor_riesgo_pais']}"
    return hashlib.sha256(key.encode()).hexdigest()
