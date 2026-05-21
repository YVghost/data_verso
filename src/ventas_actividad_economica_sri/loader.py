"""
ETL loader: Ventas por Actividad Economica SRI — Ecuador

Recibe dict[table_name -> list[dict]] desde bot.py (Saiku API)
y carga 6 tablas en la BD con deduplicacion por hash SHA-256.

Enriquece descripcion y nivel_ciiu usando utils.ciiu (hoja CIIU del XLS de referencia).

Esquema de cada tabla:
  id, codigo_ciiu, descripcion, nivel_ciiu, anio, valor, hash_registro, fecha_carga
"""

import hashlib
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.base_engine import get_master_engine
from utils.ciiu import get_map as _get_ciiu_map

# ---------------------------------------------------------------------------
# Tablas destino
# ---------------------------------------------------------------------------

_TABLES = [
    "ventas_ingresos_101",
    "ventas_vnl12_101",
    "ventas_vnl0_101",
    "ventas_exportaciones_104",
    "ventas_dependencia_103",
    "ventas_honorarios_103",
]

_DDL_TPL = """
CREATE TABLE {table} (
    id            BIGINT IDENTITY(1,1) NOT NULL,
    codigo_ciiu   NVARCHAR(20)   NOT NULL,
    descripcion   NVARCHAR(MAX)  NULL,
    nivel_ciiu    NVARCHAR(20)   NULL,
    anio          SMALLINT       NOT NULL,
    valor         FLOAT          NULL,
    hash_registro NVARCHAR(64)   NOT NULL,
    fecha_carga   DATETIME2      DEFAULT GETDATE(),
    CONSTRAINT PK_{pk} PRIMARY KEY NONCLUSTERED (id)
)"""

_IDX_TPL = "CREATE CLUSTERED INDEX CIX_{pk} ON {table} (anio, codigo_ciiu)"


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def load(data: dict) -> None:
    """
    Inserta datos en BD.

    Args:
        data: dict[table_name -> list[dict(codigo_ciiu, anio, valor, ...)]]
    """
    if not data:
        print("[ventas_sri] Sin datos para cargar.")
        return

    engine = get_master_engine()
    _ensure_tables(engine)

    total = 0
    for table, records in data.items():
        if table not in _TABLES:
            continue
        if not records:
            print(f"[ventas_sri] {table}: sin registros.")
            continue
        n = _load_table(engine, table, records)
        total += n
        print(f"[ventas_sri] {table}: {n} filas nuevas.")

    print(f"[ventas_sri] Total insertado: {total} filas.")


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

def _ensure_tables(engine) -> None:
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(engine)
    for table in _TABLES:
        if not insp.has_table(table):
            pk = table.replace("-", "_")
            with engine.begin() as conn:
                conn.execute(text(_DDL_TPL.format(table=table, pk=pk)))
                conn.execute(text(_IDX_TPL.format(table=table, pk=pk)))
            print(f"[ventas_sri] Tabla {table} creada.")
        else:
            # Ampliar descripcion si fue creada con NVARCHAR(N) < MAX
            cols = {c["name"]: c for c in insp.get_columns(table)}
            desc_col = cols.get("descripcion", {})
            type_str = str(desc_col.get("type", "")).upper()
            if "MAX" not in type_str:
                with engine.begin() as conn:
                    conn.execute(text(
                        f"ALTER TABLE {table} ALTER COLUMN descripcion NVARCHAR(MAX) NULL"
                    ))
                print(f"[ventas_sri] Columna descripcion ampliada a NVARCHAR(MAX) en {table}.")


def _get_existing_hashes(engine, table: str) -> set:
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT hash_registro FROM {table}")).fetchall()
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# Insercion
# ---------------------------------------------------------------------------

def _load_table(engine, table: str, records: list[dict]) -> int:
    existing  = _get_existing_hashes(engine, table)
    ciiu_map  = _get_ciiu_map()

    to_insert = []
    for r in records:
        codigo = str(r.get("codigo_ciiu") or "").strip()
        anio   = r.get("anio")
        if not codigo or not anio:
            continue

        h = _hash(codigo, int(anio))
        if h in existing:
            continue

        desc, nivel = ciiu_map.get(codigo, (None, None))

        to_insert.append({
            "codigo_ciiu":   codigo,
            "descripcion":   desc,
            "nivel_ciiu":    nivel,
            "anio":          int(anio),
            "valor":         r.get("valor"),
            "hash_registro": h,
        })

    if not to_insert:
        return 0

    _insert(to_insert, table, engine)
    return len(to_insert)


def _insert(records: list[dict], table: str, engine) -> None:
    cols         = list(records[0].keys())
    col_list     = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    BATCH = 2000
    with engine.begin() as conn:
        for i in range(0, len(records), BATCH):
            conn.execute(
                text(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"),
                records[i : i + BATCH],
            )


def _hash(codigo: str, anio: int) -> str:
    return hashlib.sha256(f"{codigo}|{anio}".encode()).hexdigest()
