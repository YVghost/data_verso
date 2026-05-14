"""
ETL loader: Recaudacion Mensual SRI Ecuador

Tabla: recaudacion_mensual_provincial
Columnas fuente (11 cols):
  ANIO | MES | GRUPO_IMPUESTO | SUBGRUPO_IMPUESTO | IMPUESTO |
  GRAN_CONTRIBUYENTE | CODIGO_OPERA_FAMILIA | TIPO_CONTRIBUYENTE |
  PROVINCIA | CANTON | VALOR_RECAUDADO

Variaciones por año observadas:
  - Separador: | (2017-2025) o ; (2026+)
  - Encoding:  utf-8-sig o latin-1 (auto-detectado)
  - BOM en nombre de columna (2018-2022): strip automatico
  - MES: "01 Enero" (2017-2025) o "1-ene" (2026+)
  - VALOR_RECAUDADO: "88123,17" (coma decimal) o "75.616,61" (formato europeo)

Deduplicacion por (anio, mes_num): meses ya cargados se omiten completamente.
"""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.base_engine import get_master_engine

_TABLE     = "recaudacion_mensual_provincial"
_CHUNKSIZE = 50_000

_DDL = """
CREATE TABLE recaudacion_mensual_provincial (
    id                    BIGINT IDENTITY(1,1) NOT NULL,
    anio                  INT            NOT NULL,
    mes_num               TINYINT        NOT NULL,
    mes                   NVARCHAR(30)   NOT NULL,
    grupo_impuesto        NVARCHAR(300)  NULL,
    subgrupo_impuesto     NVARCHAR(300)  NULL,
    impuesto              NVARCHAR(500)  NULL,
    gran_contribuyente    NVARCHAR(10)   NULL,
    codigo_opera_familia  NVARCHAR(100)  NULL,
    tipo_contribuyente    NVARCHAR(200)  NULL,
    provincia             NVARCHAR(100)  NULL,
    canton                NVARCHAR(200)  NULL,
    valor_recaudado       FLOAT          NULL,
    fecha_carga           DATETIME2      DEFAULT GETDATE(),
    CONSTRAINT PK_recaudacion_mensual_provincial PRIMARY KEY NONCLUSTERED (id)
)"""

_IDX = "CREATE CLUSTERED INDEX CIX_recaudacion_mensual_provincial ON recaudacion_mensual_provincial (anio, mes_num)"

# Abreviaturas de mes en español (formato 2026: "1-ene")
_MES_ABBR: dict[str, tuple[int, str]] = {
    "ene": (1,  "Enero"),     "feb": (2,  "Febrero"),
    "mar": (3,  "Marzo"),     "abr": (4,  "Abril"),
    "may": (5,  "Mayo"),      "jun": (6,  "Junio"),
    "jul": (7,  "Julio"),     "ago": (8,  "Agosto"),
    "sep": (9,  "Septiembre"),"oct": (10, "Octubre"),
    "nov": (11, "Noviembre"), "dic": (12, "Diciembre"),
}


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def load(files: list[Path]) -> None:
    if not files:
        print("[recaudacion] Sin archivos para cargar.")
        return

    engine = get_master_engine()
    _ensure_table(engine)
    existing = _get_existing_months(engine)

    total_new = 0
    for path in sorted(files):
        n = _load_file(path, engine, existing)
        total_new += n

    print(f"[recaudacion] Total: {total_new:,} filas nuevas en {_TABLE}.")


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

def _ensure_table(engine) -> None:
    from sqlalchemy import inspect as sa_inspect
    if not sa_inspect(engine).has_table(_TABLE):
        with engine.begin() as conn:
            conn.execute(text(_DDL))
            conn.execute(text(_IDX))
        print(f"[recaudacion] Tabla {_TABLE} creada.")


def _get_existing_months(engine) -> set[tuple[int, int]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT DISTINCT anio, mes_num FROM {_TABLE}")
        ).fetchall()
    return {(int(r[0]), int(r[1])) for r in rows}


# ---------------------------------------------------------------------------
# Carga por archivo
# ---------------------------------------------------------------------------

def _load_file(path: Path, engine, existing: set[tuple[int, int]]) -> int:
    year = _year_from_path(path)
    enc  = _detect_encoding(path)
    sep  = _detect_sep(path, enc)

    print(f"[recaudacion] Procesando {path.name} (enc={enc}, sep='{sep}')...")

    try:
        reader = pd.read_csv(
            path,
            sep=sep,
            encoding=enc,
            dtype=str,
            chunksize=_CHUNKSIZE,
            on_bad_lines="skip",
            low_memory=False,
        )
    except Exception as ex:
        print(f"[recaudacion] Error abriendo {path.name}: {ex}")
        return 0

    inserted = 0

    for chunk in reader:
        # Normalizar nombres de columna (strip BOM y no-ASCII, mayusculas)
        chunk.columns = [_norm_col(c) for c in chunk.columns]

        # Añadir ANIO desde nombre de archivo si la columna no existe
        if "ANIO" not in chunk.columns:
            chunk["ANIO"] = str(year)

        chunk = _parse_mes(chunk)
        if chunk.empty:
            continue

        chunk = _parse_valor(chunk)

        # Filtrar meses ya cargados
        anio_arr  = pd.to_numeric(chunk["ANIO"], errors="coerce").fillna(0).astype(int)
        mes_arr   = chunk["mes_num"].astype(int)
        keep_mask = pd.Series(
            [(int(a), int(m)) not in existing for a, m in zip(anio_arr, mes_arr)],
            index=chunk.index,
        )
        chunk = chunk[keep_mask]
        if chunk.empty:
            continue

        records = _to_records(chunk)
        _insert(records, engine)
        inserted += len(records)

    if inserted:
        print(f"[recaudacion] {path.name}: {inserted:,} filas insertadas.")
    else:
        print(f"[recaudacion] {path.name}: sin filas nuevas.")

    return inserted


# ---------------------------------------------------------------------------
# Deteccion de formato
# ---------------------------------------------------------------------------

def _detect_encoding(path: Path) -> str:
    """Intenta UTF-8; si falla con los primeros 4 KB usa latin-1."""
    try:
        with open(path, "rb") as f:
            f.read(4096).decode("utf-8")
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "latin-1"


def _detect_sep(path: Path, enc: str) -> str:
    """Devuelve '|' o ';' segun cual aparece mas veces en la primera linea."""
    try:
        with open(path, "r", encoding=enc, errors="replace") as f:
            first = f.readline()
        return "|" if first.count("|") >= first.count(";") else ";"
    except OSError:
        return "|"


def _norm_col(c: str) -> str:
    """Elimina BOM y caracteres no-ASCII al inicio del nombre de columna."""
    c = c.strip()
    c = re.sub(r"^[^\x20-\x7E]+", "", c)  # strip leading non-printable-ASCII
    return c.strip().upper()


# ---------------------------------------------------------------------------
# Transformaciones
# ---------------------------------------------------------------------------

def _parse_mes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Soporta dos formatos:
      - "01 Enero"   -> mes_num=1,  mes="Enero"   (2017-2025)
      - "1-ene"      -> mes_num=1,  mes="Enero"   (2026+)
    """
    mes_str = df["MES"].astype(str).str.strip()

    # Formato "01 Enero" / "1 Enero"
    ext1 = mes_str.str.extract(r"^(\d{1,2})\s+(.+)$")
    # Formato "1-ene"
    ext2 = mes_str.str.extract(r"^(\d{1,2})-([a-zA-Z]+)$")

    df = df.copy()
    mes_num = pd.array([None] * len(df), dtype=object)
    mes_nom = pd.array([None] * len(df), dtype=object)

    for i, (v1, v2, raw2) in enumerate(
        zip(ext1[0], ext1[1], ext2[1])
    ):
        if pd.notna(v1) and pd.notna(v2):          # formato largo
            mes_num[i] = int(v1)
            mes_nom[i] = str(v2).strip()
        elif pd.notna(raw2):                         # formato abreviado
            abbr = str(raw2).lower()
            if abbr in _MES_ABBR:
                mes_num[i], mes_nom[i] = _MES_ABBR[abbr]

    df["mes_num"] = mes_num
    df["mes"]     = mes_nom
    df = df.dropna(subset=["mes_num", "mes"])
    df["mes_num"] = df["mes_num"].astype(int)
    return df


def _parse_valor(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte VALOR_RECAUDADO a float:
      - "88123,17"   -> 88123.17   (coma como decimal)
      - "75.616,61"  -> 75616.61   (formato europeo: punto miles, coma decimal)
      - ",0000"      -> 0.0
    """
    def _to_float(v) -> float | None:
        s = str(v).strip() if v is not None else ""
        if not s or s.lower() in ("nan", "none", ""):
            return None
        if "." in s and "," in s:
            # Formato europeo: punto = separador miles, coma = decimal
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", ".")
        if s.startswith("."):
            s = "0" + s
        try:
            return float(s)
        except ValueError:
            return None

    df = df.copy()
    df["valor_recaudado"] = df["VALOR_RECAUDADO"].apply(_to_float)
    return df


# ---------------------------------------------------------------------------
# Conversion a registros e insercion
# ---------------------------------------------------------------------------

def _to_records(df: pd.DataFrame) -> list[dict]:
    anio_arr = pd.to_numeric(df["ANIO"], errors="coerce").fillna(0).astype(int).tolist()
    mes_num  = df["mes_num"].astype(int).tolist()
    mes      = df["mes"].tolist()
    valor    = df["valor_recaudado"].tolist()

    str_src = [
        ("GRUPO_IMPUESTO",       "grupo_impuesto"),
        ("SUBGRUPO_IMPUESTO",    "subgrupo_impuesto"),
        ("IMPUESTO",             "impuesto"),
        ("GRAN_CONTRIBUYENTE",   "gran_contribuyente"),
        ("CODIGO_OPERA_FAMILIA", "codigo_opera_familia"),
        ("TIPO_CONTRIBUYENTE",   "tipo_contribuyente"),
        ("PROVINCIA",            "provincia"),
        ("CANTON",               "canton"),
    ]
    str_arrays = {dst: df[src].tolist() for src, dst in str_src if src in df.columns}

    records = []
    for i in range(len(df)):
        rec: dict = {
            "anio":           anio_arr[i],
            "mes_num":        mes_num[i],
            "mes":            str(mes[i]) if mes[i] is not None else "",
            "valor_recaudado": _nan_to_none(valor[i]),
        }
        for dst, arr in str_arrays.items():
            rec[dst] = _clean_str(arr[i])
        records.append(rec)

    return records


def _insert(records: list[dict], engine) -> None:
    if not records:
        return
    cols         = list(records[0].keys())
    col_list     = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    with engine.begin() as conn:
        conn.execute(
            text(f"INSERT INTO {_TABLE} ({col_list}) VALUES ({placeholders})"),
            records,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _year_from_path(path: Path) -> int:
    m = re.search(r"(\d{4})", path.stem)
    return int(m.group(1)) if m else 0


def _nan_to_none(v):
    if v is None:
        return None
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return None
    return v


def _clean_str(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("nan", "none") else None
