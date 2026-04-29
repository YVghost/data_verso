"""
ETL: ENEMDU Trimestral y Mensual — Mercado Laboral (INEC)
Flujo: CSVs extraídos → 8 tablas finales (trimestral + mensual en las mismas tablas)

Tablas:
  empleo_poblacion      ← 1. Poblaciones.csv
  empleo_tasas          ← 2. Tasas.csv
  empleo_caracterizacion ← 3.1-3.5 Caracterización *.csv  (columna tipo_empleo)
  empleo_sectorizacion  ← 4. Sectorización del Empleo.csv

Columna tipo_periodo: 'trimestral' | 'mensual'
Columna tipo_empleo (solo empleo_caracterizacion):
  'empleados' | 'pleno' | 'subempleo' | 'no_pleno' | 'desempleo'

Layouts del CSV:
  Trimestral (files 1-2):
    col 0 = trimestre ("IV - 2020"), col 1 = indicador, cols 2-22 = 21 breakdowns
  Mensual (files 1-2):
    col 0 = encuesta, col 1 = periodo ("dic-07"), col 2 = indicador, cols 3-7 = 5 breakdowns
  Caract/Sector (ambos): transposed — periodos como cabecera de columnas desde col 2+
    Trimestral: "IV - 2020"   |   Mensual: "dic-07"
"""

import re
import sys
import hashlib
import logging
from datetime import date as _date
from pathlib import Path

import pandas as pd
from sqlalchemy import text, inspect as sa_inspect

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.base_engine import get_master_engine

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}

_MESES_ES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4,
    "may": 5, "jun": 6, "jul": 7, "ago": 8,
    "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

_TRIMESTRE_RE = re.compile(r"^(IV|III|II|I)\s*[-–]\s*(\d{4})$", re.IGNORECASE)
_MENSUAL_RE   = re.compile(r"^([a-z]{3})-(\d{2})$", re.IGNORECASE)

# Positional column map for trimestral files 1 & 2
# col 0 = trimestre, col 1 = indicador, cols 2-22 = 21 breakdowns
_POB_COLS_TRIMESTRAL = [
    (2,  "nacional_total"),
    (3,  "area_urbano"),
    (4,  "area_rural"),
    (5,  "dom_quito"),
    (6,  "dom_guayaquil"),
    (7,  "dom_cuenca"),
    (8,  "dom_machala"),
    (9,  "dom_ambato"),
    (10, "sexo_hombre"),
    (11, "sexo_mujer"),
    (12, "edad_15_24"),
    (13, "edad_25_34"),
    (14, "edad_35_44"),
    (15, "edad_45_64"),
    (16, "edad_65_mas"),
    (17, "etnia_indigena"),
    (18, "etnia_afroecuatoriano"),
    (19, "etnia_mestizo"),
    (20, "etnia_blanco"),
    (21, "etnia_montubio"),
    (22, "etnia_otro"),
]

# Positional column map for mensual files 1 & 2
# col 0 = encuesta, col 1 = periodo, col 2 = indicador, cols 3-7 = 5 breakdowns
# Columns not listed here → NULL (dom_*, edad_*, etnia_*)
_POB_COLS_MENSUAL = [
    (3, "nacional_total"),
    (4, "area_urbano"),
    (5, "area_rural"),
    (6, "sexo_hombre"),
    (7, "sexo_mujer"),
]

# All value field names for files 1 & 2 (derived from trimestral map)
_POB_ALL_FIELDS = [col for _, col in _POB_COLS_TRIMESTRAL]

# ---------------------------------------------------------------------------
# DDL — tipo_periodo is the 4th column (after trimestre, anio, trimestre_num)
# Tables are ordered by anio, trimestre_num, then tipo_periodo
# ---------------------------------------------------------------------------

_DDL_WIDE_INT = """
    trimestre             NVARCHAR(20)  NULL,
    anio                  INT           NOT NULL,
    trimestre_num         TINYINT       NOT NULL,
    tipo_periodo          NVARCHAR(20)  NOT NULL,
    fecha_mensual         DATE          NULL,
    indicador             NVARCHAR(300) NOT NULL,
    nacional_total        BIGINT,
    area_urbano           BIGINT,
    area_rural            BIGINT,
    dom_quito             BIGINT,
    dom_guayaquil         BIGINT,
    dom_cuenca            BIGINT,
    dom_machala           BIGINT,
    dom_ambato            BIGINT,
    sexo_hombre           BIGINT,
    sexo_mujer            BIGINT,
    edad_15_24            BIGINT,
    edad_25_34            BIGINT,
    edad_35_44            BIGINT,
    edad_45_64            BIGINT,
    edad_65_mas           BIGINT,
    etnia_indigena        BIGINT,
    etnia_afroecuatoriano BIGINT,
    etnia_mestizo         BIGINT,
    etnia_blanco          BIGINT,
    etnia_montubio        BIGINT,
    etnia_otro            BIGINT,
    hash_registro         NVARCHAR(64)  NOT NULL,
    fecha_carga           DATETIME2     NOT NULL DEFAULT GETDATE()
"""

_DDL_WIDE_FLOAT = """
    trimestre             NVARCHAR(20)  NULL,
    anio                  INT           NOT NULL,
    trimestre_num         TINYINT       NOT NULL,
    tipo_periodo          NVARCHAR(20)  NOT NULL,
    fecha_mensual         DATE          NULL,
    indicador             NVARCHAR(300) NOT NULL,
    nacional_total        FLOAT,
    area_urbano           FLOAT,
    area_rural            FLOAT,
    dom_quito             FLOAT,
    dom_guayaquil         FLOAT,
    dom_cuenca            FLOAT,
    dom_machala           FLOAT,
    dom_ambato            FLOAT,
    sexo_hombre           FLOAT,
    sexo_mujer            FLOAT,
    edad_15_24            FLOAT,
    edad_25_34            FLOAT,
    edad_35_44            FLOAT,
    edad_45_64            FLOAT,
    edad_65_mas           FLOAT,
    etnia_indigena        FLOAT,
    etnia_afroecuatoriano FLOAT,
    etnia_mestizo         FLOAT,
    etnia_blanco          FLOAT,
    etnia_montubio        FLOAT,
    etnia_otro            FLOAT,
    hash_registro         NVARCHAR(64)  NOT NULL,
    fecha_carga           DATETIME2     NOT NULL DEFAULT GETDATE()
"""

_DDL_CARACT = """
    trimestre      NVARCHAR(20)  NULL,
    anio           INT           NOT NULL,
    trimestre_num  TINYINT       NOT NULL,
    tipo_periodo   NVARCHAR(20)  NOT NULL,
    fecha_mensual  DATE          NULL,
    tipo_empleo    NVARCHAR(50)  NOT NULL,
    categoria      NVARCHAR(200) NOT NULL,
    subcategoria   NVARCHAR(300) NOT NULL,
    porcentaje     FLOAT,
    hash_registro  NVARCHAR(64)  NOT NULL,
    fecha_carga    DATETIME2     NOT NULL DEFAULT GETDATE()
"""

# Valores de tipo_empleo por archivo fuente
_CARACT_TIPO_EMPLEO = {
    "caract_empleados":     "empleados",
    "caract_adec_pleno":    "pleno",
    "caract_subempleo":     "subempleo",
    "caract_otro_no_pleno": "no_pleno",
    "caract_desempleo":     "desempleo",
}

_DDL_SECTOR = """
    trimestre      NVARCHAR(20)  NULL,
    anio           INT           NOT NULL,
    trimestre_num  TINYINT       NOT NULL,
    tipo_periodo   NVARCHAR(20)  NOT NULL,
    fecha_mensual  DATE          NULL,
    ambito         NVARCHAR(100) NOT NULL,
    sector         NVARCHAR(200) NOT NULL,
    porcentaje     FLOAT,
    hash_registro  NVARCHAR(64)  NOT NULL,
    fecha_carga    DATETIME2     NOT NULL DEFAULT GETDATE()
"""

_TABLE_DDLS = {
    "empleo_poblacion":     _DDL_WIDE_INT,
    "empleo_tasas":         _DDL_WIDE_FLOAT,
    "empleo_caracterizacion": _DDL_CARACT,
    "empleo_sectorizacion": _DDL_SECTOR,
}

# Columnas del índice clúster por tabla (las demás usan el default)
_TABLE_CLUSTER_COLS = {
    "empleo_caracterizacion": "anio, trimestre_num, tipo_periodo, tipo_empleo",
}

# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

def _parse_periodo(s: str):
    """
    Unified parser for both period formats.
    Trimestral "IV - 2020"  → (2020, 4)
    Mensual    "dic-07"     → (2007, 12)
    Returns (anio, periodo_num) or (None, None).
    """
    s = str(s).strip()
    m = _TRIMESTRE_RE.match(s)
    if m:
        return int(m.group(2)), _ROMAN.get(m.group(1).upper())
    m = _MENSUAL_RE.match(s)
    if m:
        mes_num = _MESES_ES.get(m.group(1).lower())
        if mes_num:
            return 2000 + int(m.group(2)), mes_num
    return None, None


def _periodo_a_fecha(year: int, num: int):
    """Para datos mensuales: (2007, 12) → date(2007, 12, 1). Para trimestral → None."""
    return _date(year, num, 1)


def _get_tipo_periodo(path: Path) -> str:
    """Infer tipo_periodo from the parent folder name.
    downloads/empleo/{year}/I/    → 'trimestral'
    downloads/empleo/{year}/202603/ → 'mensual'
    """
    folder = path.parent.name
    if folder.upper() in _ROMAN:
        return "trimestral"
    if re.match(r"^\d{6}$", folder):
        return "mensual"
    return "desconocido"

# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def _clean_int(s: str):
    """'17.675.512' → 17675512  |  '-' / '' / 'nan' → None."""
    s = str(s).strip()
    if s in ("-", "", "nan"):
        return None
    try:
        return int(s.replace(".", "").replace(",", ""))
    except ValueError:
        return None


def _clean_float(s: str):
    """'61,7' or '59,2%' → 61.7  |  '-' / '' / 'nan' → None."""
    s = str(s).strip().rstrip("%").strip()
    if s in ("-", "", "nan"):
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _hash(rec: dict) -> str:
    key = "|".join(str(v) for v in rec.values())
    return hashlib.sha256(key.encode()).hexdigest()


def _collect_periodo_cols(header_row, start_col: int = 2) -> list:
    """
    Extracts (col_idx, periodo_str, anio, periodo_num) from a header row.
    Handles both trimestral ("IV - 2020") and mensual ("dic-07") labels.
    Skips empty cells and duplicate period labels.
    """
    result = []
    seen   = set()
    for idx in range(start_col, len(header_row)):
        t = str(header_row.iloc[idx]).strip()
        if not t or t == "nan":
            continue
        if t in seen:
            log.debug(f"[empleo] Periodo duplicado ignorado: {t}")
            continue
        year, num = _parse_periodo(t)
        if year is None:
            continue
        seen.add(t)
        result.append((idx, t, year, num))
    return result


def _ffill_col(series) -> list:
    """Forward-fill treating '' and 'nan' as missing."""
    out, last = [], ""
    for v in series:
        v = str(v).strip()
        if v and v != "nan":
            last = v
        out.append(last)
    return out

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_pob_tasas(path: Path, file_key: str, tipo_periodo: str) -> pd.DataFrame:
    """
    Parse files 1 (Poblaciones) and 2 (Tasas) for both trimestral and mensual.

    Trimestral layout (skiprows=3):
      col 0 = trimestre, col 1 = indicador, cols 2-22 = 21 breakdowns

    Mensual layout (skiprows=3):
      col 0 = 'ENEMDU', col 1 = periodo, col 2 = indicador, cols 3-7 = 5 breakdowns
      cols not present in mensual → NULL
    """
    is_poblacion = file_key == "poblacion"
    clean_val    = _clean_int if is_poblacion else _clean_float

    col_map = _POB_COLS_TRIMESTRAL if tipo_periodo == "trimestral" else _POB_COLS_MENSUAL

    df = pd.read_csv(
        path, sep=";", encoding="latin-1",
        header=None, skiprows=3,
        dtype=str, keep_default_na=False,
    )

    records = []
    for _, row in df.iterrows():
        if tipo_periodo == "trimestral":
            periodo_str = str(row.iloc[0]).strip()
            indicador   = str(row.iloc[1]).strip()
        else:
            periodo_str = str(row.iloc[1]).strip()
            indicador   = str(row.iloc[2]).strip()

        if not periodo_str or periodo_str == "nan":
            continue
        year, num = _parse_periodo(periodo_str)
        if year is None:
            continue
        if not indicador or indicador == "nan":
            continue

        rec = {
            "trimestre":    periodo_str if tipo_periodo == "trimestral" else None,
            "anio":          year,
            "trimestre_num": num,
            "tipo_periodo":  tipo_periodo,
            "fecha_mensual": _periodo_a_fecha(year, num) if tipo_periodo == "mensual" else None,
            "indicador":     indicador,
        }
        # Initialize all value columns to None (mensual will leave extras as None)
        for col_name in _POB_ALL_FIELDS:
            rec[col_name] = None
        # Fill available columns from this layout
        for col_idx, col_name in col_map:
            raw = str(row.iloc[col_idx]) if col_idx < len(row) else "-"
            rec[col_name] = clean_val(raw)

        rec["hash_registro"] = _hash(rec)
        records.append(rec)

    return pd.DataFrame(records)


def _parse_caract(path: Path, tipo_periodo: str, tipo_empleo: str) -> pd.DataFrame:
    """
    Parse files 3.1-3.5 (caracterización, transposed format) → empleo_caracterizacion.

    Row 0 (after skipping blank): header with period labels from col 2 onward.
    Rows 1+: categoria ; subcategoria ; val_0 ; val_1 ; …
    categoria is blank for continuation rows → forward-filled.
    Works for both trimestral ("IV - 2020") and mensual ("dic-07") labels.
    tipo_empleo: 'empleados' | 'pleno' | 'subempleo' | 'no_pleno' | 'desempleo'
    """
    df = pd.read_csv(
        path, sep=";", encoding="latin-1",
        header=None, skiprows=1,
        dtype=str, keep_default_na=False,
    )

    periodo_cols = _collect_periodo_cols(df.iloc[0], start_col=2)
    data         = df.iloc[1:].reset_index(drop=True)
    categorias   = _ffill_col(data.iloc[:, 0])

    records = []
    for row_idx, row in data.iterrows():
        cat    = categorias[row_idx]
        subcat = str(row.iloc[1]).strip()
        if not cat or not subcat or subcat in ("", "nan"):
            continue

        for col_idx, periodo, year, num in periodo_cols:
            if col_idx >= len(row):
                continue
            val = _clean_float(str(row.iloc[col_idx]))
            rec = {
                "trimestre":    periodo if tipo_periodo == "trimestral" else None,
                "anio":          year,
                "trimestre_num": num,
                "tipo_periodo":  tipo_periodo,
                "fecha_mensual": _periodo_a_fecha(year, num) if tipo_periodo == "mensual" else None,
                "tipo_empleo":   tipo_empleo,
                "categoria":     cat,
                "subcategoria":  subcat,
                "porcentaje":    val,
            }
            rec["hash_registro"] = _hash(rec)
            records.append(rec)

    return pd.DataFrame(records)


def _parse_sector(path: Path, tipo_periodo: str) -> pd.DataFrame:
    """
    Parse file 4 (Sectorización del Empleo).

    Row 0 (after skipping blank): header with period labels from col 2 onward.
    Rows 1+: ambito ; sector ; val_0 ; val_1 ; …
    ambito is blank for continuation rows → forward-filled.
    Works for both trimestral and mensual period labels.
    """
    df = pd.read_csv(
        path, sep=";", encoding="latin-1",
        header=None, skiprows=1,
        dtype=str, keep_default_na=False,
    )

    periodo_cols = _collect_periodo_cols(df.iloc[0], start_col=2)
    data         = df.iloc[1:].reset_index(drop=True)
    ambitos      = _ffill_col(data.iloc[:, 0])

    records = []
    for row_idx, row in data.iterrows():
        ambito = ambitos[row_idx]
        sector = str(row.iloc[1]).strip()
        if not ambito or not sector or sector in ("", "nan"):
            continue

        for col_idx, periodo, year, num in periodo_cols:
            if col_idx >= len(row):
                continue
            val = _clean_float(str(row.iloc[col_idx]))
            rec = {
                "trimestre":    periodo if tipo_periodo == "trimestral" else None,
                "anio":          year,
                "trimestre_num": num,
                "tipo_periodo":  tipo_periodo,
                "fecha_mensual": _periodo_a_fecha(year, num) if tipo_periodo == "mensual" else None,
                "ambito":        ambito,
                "sector":        sector,
                "porcentaje":    val,
            }
            rec["hash_registro"] = _hash(rec)
            records.append(rec)

    return pd.DataFrame(records)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _ensure_tables(engine) -> None:
    inspector = sa_inspect(engine)
    existing  = {t.lower() for t in inspector.get_table_names()}
    with engine.begin() as conn:
        for table, cols_ddl in _TABLE_DDLS.items():
            if table.lower() not in existing:
                # PK no clústered → el índice clúster físico es por (anio, trimestre_num, tipo_periodo)
                conn.execute(text(f"""
                    CREATE TABLE {table} (
                        id BIGINT IDENTITY(1,1) NOT NULL
                            CONSTRAINT PK_{table} PRIMARY KEY NONCLUSTERED,
                        {cols_ddl.strip()}
                    )
                """))
                cluster_cols = _TABLE_CLUSTER_COLS.get(
                    table, "anio, trimestre_num, tipo_periodo"
                )
                conn.execute(text(f"""
                    CREATE CLUSTERED INDEX CIX_{table}
                    ON {table} ({cluster_cols})
                """))
                log.info(f"[empleo] Tabla creada: {table}")


def _ensure_columns(engine) -> None:
    """Non-destructive migration: añade columnas nuevas y ajusta constraints."""
    inspector = sa_inspect(engine)
    with engine.begin() as conn:
        for table in _TABLE_DDLS:
            try:
                cols = {c["name"].lower(): c for c in inspector.get_columns(table)}
            except Exception:
                continue  # table doesn't exist yet

            # trimestre debe permitir NULL (para datos mensuales)
            if "trimestre" in cols and not cols["trimestre"]["nullable"]:
                conn.execute(text(
                    f"ALTER TABLE {table} ALTER COLUMN trimestre NVARCHAR(20) NULL"
                ))
                log.info(f"[empleo] trimestre cambiado a NULL en {table}")

            if "tipo_periodo" not in cols:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD tipo_periodo NVARCHAR(20) NOT NULL DEFAULT 'trimestral'"
                ))
                log.info(f"[empleo] Columna tipo_periodo añadida a {table}")

            if "fecha_mensual" not in cols:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD fecha_mensual DATE NULL"
                ))
                log.info(f"[empleo] Columna fecha_mensual añadida a {table}")

            if table == "empleo_caracterizacion" and "tipo_empleo" not in cols:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD tipo_empleo NVARCHAR(50) NOT NULL DEFAULT 'empleados'"
                ))
                log.info(f"[empleo] Columna tipo_empleo añadida a {table}")


def _insert_new(engine, table: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    with engine.connect() as conn:
        existing_hashes = {
            row[0]
            for row in conn.execute(text(f"SELECT hash_registro FROM {table}"))
        }

    new_df = df[~df["hash_registro"].isin(existing_hashes)].copy()
    if new_df.empty:
        return 0

    # Ordenar por año → trimestre_num → tipo_periodo antes de insertar,
    # así la inserción sigue el mismo orden que el índice clúster.
    new_df = new_df.sort_values(["anio", "trimestre_num", "tipo_periodo"]).reset_index(drop=True)

    new_df.to_sql(table, engine, if_exists="append", index=False)
    return len(new_df)

# ---------------------------------------------------------------------------
# File identification
# ---------------------------------------------------------------------------

def _identify_file(name: str):
    """
    Map a CSV filename to (file_key, table_name, tipo_empleo).
    tipo_empleo is None for non-characterization files.
    """
    n = name.lower()
    if "poblacion" in n:
        return "poblacion",            "empleo_poblacion",       None
    if "tasas" in n:
        return "tasas",                "empleo_tasas",           None
    if "3.1" in n or "empleados" in n:
        return "caract_empleados",     "empleo_caracterizacion", "empleados"
    if "3.2" in n or "adec_pleno" in n:
        return "caract_adec_pleno",    "empleo_caracterizacion", "pleno"
    if "3.3" in n or "subempleo" in n:
        return "caract_subempleo",     "empleo_caracterizacion", "subempleo"
    if "3.4" in n or "ot. no" in n or "otro no" in n:
        return "caract_otro_no_pleno", "empleo_caracterizacion", "no_pleno"
    if "3.5" in n or "desempleo" in n:
        return "caract_desempleo",     "empleo_caracterizacion", "desempleo"
    if "sectoriz" in n:
        return "sectorizacion",        "empleo_sectorizacion",   None
    return None, None, None

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def load(csv_paths: list, start_year: int = None, end_year: int = None) -> None:
    """
    Procesa CSVs de ENEMDU (trimestral y mensual) y los carga en la BD.
    - tipo_periodo se infiere del nombre de la carpeta padre:
        I / II / III / IV  → 'trimestral'
        YYYYMM (6 dígitos) → 'mensual'
    - start_year / end_year filtran sobre el contenido del CSV, no la carpeta.
    - Idempotente: inserta solo filas cuyo hash_registro no existe en la tabla.
    """
    if not csv_paths:
        log.info("[empleo] Sin archivos CSV para procesar.")
        return

    engine = get_master_engine()
    _ensure_tables(engine)
    _ensure_columns(engine)

    # Deduplicar por (carpeta, nombre): evita reprocesar el mismo archivo
    # si el mismo período fue descargado más de una vez.
    unique_files: dict[tuple, Path] = {}
    for p in csv_paths:
        p   = Path(p)
        key = (p.parent.name, p.name)
        if key not in unique_files:
            unique_files[key] = p

    total_inserted = 0

    for (folder, fname), path in unique_files.items():
        file_key, table, tipo_empleo = _identify_file(fname)
        if not file_key:
            log.warning(f"[empleo] Archivo no reconocido, se omite: {fname}")
            continue

        tipo_periodo = _get_tipo_periodo(path)
        log.info(f"[empleo] Procesando [{tipo_periodo}] {fname}  →  {table}")

        try:
            if file_key in ("poblacion", "tasas"):
                df = _parse_pob_tasas(path, file_key, tipo_periodo)
            elif file_key.startswith("caract_"):
                df = _parse_caract(path, tipo_periodo, tipo_empleo)
            else:
                df = _parse_sector(path, tipo_periodo)
        except Exception as ex:
            log.error(f"[empleo] Error parseando {fname}: {ex}", exc_info=True)
            continue

        if df.empty:
            log.info(f"[empleo] {table}: sin datos tras el parseo")
            continue

        if start_year:
            df = df[df["anio"] >= start_year]
        if end_year:
            df = df[df["anio"] <= end_year]

        if df.empty:
            log.info(f"[empleo] {table}: sin datos en el rango de años especificado")
            continue

        n = _insert_new(engine, table, df)
        log.info(f"[empleo] {table}: {n} filas nuevas insertadas")
        total_inserted += n

    log.info(f"[empleo] Carga completada — total filas insertadas: {total_inserted}")
