"""
Utilidad: Clasificador Industrial Internacional Uniforme (CIIU) v4.0 Ecuador

Lee la hoja "CIIU" del archivo de referencia del SRI y construye un dict
con el mapeo codigo -> (descripcion, nivel) para enriquecer las tablas
de ventas por actividad economica.

Uso:
    from utils.ciiu import get_map

    m = get_map()
    desc, nivel = m.get("A011111", (None, None))
"""

import functools
from pathlib import Path

import xlrd

# Ruta al archivo de referencia CIIU (relativa a la raiz del proyecto)
_XLS_PATH = Path(__file__).resolve().parents[1] / "CIUS Para ventas por actividad economicaFInal 2.xls"

# Columnas en la hoja CIIU (0-indexed)
_COL_CODIGO = 1
_COL_DESC   = 2
_COL_NIVEL  = 3
_FIRST_ROW  = 3   # fila donde comienzan los datos (0-indexed)


@functools.lru_cache(maxsize=1)
def get_map() -> dict[str, tuple[str | None, str | None]]:
    """
    Retorna dict {codigo_ciiu: (descripcion, nivel)}.
    El resultado se cachea en memoria tras la primera llamada.
    Retorna dict vacio si el archivo no existe.
    """
    if not _XLS_PATH.exists():
        print(f"[ciiu] Archivo de referencia no encontrado: {_XLS_PATH}")
        return {}

    try:
        wb = xlrd.open_workbook(str(_XLS_PATH), encoding_override="cp1252")
    except Exception:
        try:
            wb = xlrd.open_workbook(str(_XLS_PATH))
        except Exception as exc:
            print(f"[ciiu] No se pudo abrir el archivo: {exc}")
            return {}

    # Buscar la hoja "CIIU"
    ws = None
    for name in wb.sheet_names():
        if name.strip().upper() == "CIIU":
            ws = wb.sheet_by_name(name)
            break

    if ws is None:
        print("[ciiu] Hoja 'CIIU' no encontrada en el archivo.")
        return {}

    mapping: dict[str, tuple[str | None, str | None]] = {}

    for ri in range(_FIRST_ROW, ws.nrows):
        codigo = str(ws.cell_value(ri, _COL_CODIGO)).strip()
        if not codigo:
            continue

        desc  = str(ws.cell_value(ri, _COL_DESC)).strip() or None
        nivel = str(ws.cell_value(ri, _COL_NIVEL)).strip() or None

        mapping[codigo] = (desc, nivel)

    return mapping
