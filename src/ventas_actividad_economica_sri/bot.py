"""
Bot: Ventas por Actividad Economica SRI — Ecuador (Saiku REST API)

Fuente  : Saiku REST API — srienlinea.sri.gob.ec/saiku/
Auth    : Spring Security form-login (admin/admin — cuenta publica Saiku)
Periodo : disponible desde 2020 en D101/D104, desde años previos en D103
Cubos   : D101, D103, D104  (dentro del datasource Declaracion)

Flujo por metrica:
  1. Login con admin/admin a /saiku/j_spring_security_check
  2. Crear query QM en /saiku/rest/saiku/api/query/{uuid}
  3. POST MDX a /query/{uuid}/result/flattened
  4. Parsear cellset JSON (maneja valores null heredados de fila anterior)
  5. Retornar dict[table_name -> list[dict(codigo_ciiu, anio, valor)]]

Metricas:
  ventas_ingresos_101       — [D101] Total Ingresos (699)
  ventas_vnl12_101          — [D101] Ventas Netas Locales 12% (601)
  ventas_vnl0_101           — [D101] Ventas Netas Locales 0% (602)
  ventas_exportaciones_104  — [D104] Total Ventas y Exportaciones (419)
  ventas_dependencia_103    — [D103] 270 En Relacion de Dependencia
  ventas_honorarios_103     — [D103] 320 Honorarios Profesionales
"""

import time
import uuid
import requests
from pathlib import Path

FIRST_YEAR   = 2018
DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "ventas_actividad_economica_sri"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

_BASE    = "https://srienlinea.sri.gob.ec/saiku"
_API     = f"{_BASE}/rest/saiku/api"
_LOGIN   = f"{_BASE}/j_spring_security_check"
_TIMEOUT = 180
_RETRY   = 3
_DELAY   = 3.0

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; data_verso/1.0)",
    "Accept":     "application/json",
    "Referer":    "https://srienlinea.sri.gob.ec/saiku-ui/",
}

# ---------------------------------------------------------------------------
# Definicion de metricas
# ---------------------------------------------------------------------------

_METRICS = [
    {
        "ds":       "declaracion101",
        "cube":     "D101",
        "measure":  "[Measures].[TOTAL INGRESOS (699)]",
        "table":    "ventas_ingresos_101",
        "dim_anio": "[ANIO FISCAL].[ANIO FISCAL].Members",
    },
    {
        "ds":       "declaracion101",
        "cube":     "D101",
        "measure":  "[Measures].[VENTAS NETAS LOCALES 12% (601)]",
        "table":    "ventas_vnl12_101",
        "dim_anio": "[ANIO FISCAL].[ANIO FISCAL].Members",
    },
    {
        "ds":       "declaracion101",
        "cube":     "D101",
        "measure":  "[Measures].[VENTAS NETAS LOCALES  0% (602)]",  # doble espacio
        "table":    "ventas_vnl0_101",
        "dim_anio": "[ANIO FISCAL].[ANIO FISCAL].Members",
    },
    {
        "ds":       "declaracion104",
        "cube":     "D104",
        "measure":  "[Measures].[TOTAL VENTAS Y EXPORTACIONES (419)]",
        "table":    "ventas_exportaciones_104",
        "dim_anio": "[ANIO FISCAL].[ANIO FISCAL].Members",
    },
    {
        "ds":       "declaracion103",
        "cube":     "D103",
        "measure":  "[Measures].[270 EN RELACION DE DEPENDENCIA]",
        "table":    "ventas_dependencia_103",
        "dim_anio": "[PERIODO FISCAL].[PERIODO FISCAL.Periodo].[ANIO_FISCAL].Members",
    },
    {
        "ds":       "declaracion103",
        "cube":     "D103",
        "measure":  "[Measures].[320 HONORARIOS PROFESIONALES ]",  # espacio al final
        "table":    "ventas_honorarios_103",
        "dim_anio": "[PERIODO FISCAL].[PERIODO FISCAL.Periodo].[ANIO_FISCAL].Members",
    },
]

_ACT_LEVEL = "[ACTIVIDAD ECONOMICA].[ACTIVIDAD ECONOMICA].[CODIGO_OPERA_ACTIVIDAD_ECO].Members"


# ---------------------------------------------------------------------------
# Autenticacion y sesion
# ---------------------------------------------------------------------------

def _login(session: requests.Session) -> bool:
    """Login Spring Security con credenciales Saiku por defecto."""
    try:
        r = session.post(
            _LOGIN,
            data={"j_username": "admin", "j_password": "admin"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
            allow_redirects=True,
        )
        # Login exitoso si NO redirige a login_error
        return "login_error" not in r.url
    except requests.RequestException as exc:
        print(f"[ventas_sri] Error de login: {exc}")
        return False


def _create_qm(session: requests.Session, ds: str, cube: str) -> str | None:
    """Crea un query QM vacio y retorna el queryId."""
    qid = uuid.uuid4().hex[:16]
    payload = {
        "connection": ds,
        "catalog":    "Declaracion",
        "schema":     "Declaracion",
        "cube":       cube,
    }
    for attempt in range(1, _RETRY + 1):
        try:
            r = session.post(
                f"{_API}/query/{qid}",
                data=payload,
                headers=_HEADERS,
                timeout=60,
            )
            if r.ok:
                return qid
            print(f"  [ventas_sri] create QM intento {attempt}: HTTP {r.status_code}")
        except requests.RequestException as exc:
            print(f"  [ventas_sri] create QM error: {exc}")
        if attempt < _RETRY:
            time.sleep(2 ** attempt)
    return None


# ---------------------------------------------------------------------------
# Construccion y ejecucion MDX
# ---------------------------------------------------------------------------

def _build_mdx(m: dict) -> str:
    """MDX: CrossJoin(anio, actividad_economica) ON ROWS, 1 medida ON COLUMNS."""
    return (
        f"SELECT NON EMPTY {{{m['measure']}}} ON COLUMNS, "
        f"NON EMPTY CrossJoin({m['dim_anio']}, {_ACT_LEVEL}) ON ROWS "
        f"FROM [{m['cube']}]"
    )


def _fetch_cellset(session: requests.Session, qid: str, mdx: str) -> list | None:
    """Ejecuta MDX via POST /result/flattened y retorna el cellset."""
    url = f"{_API}/query/{qid}/result/flattened"
    for attempt in range(1, _RETRY + 1):
        try:
            r = session.post(
                url,
                data={"mdx": mdx, "limit": 0},
                headers=_HEADERS,
                timeout=_TIMEOUT,
            )
            if r.ok:
                data = r.json()
                if data.get("error"):
                    print(f"  [ventas_sri] MDX error: {data['error'][:200]}")
                    return None
                return data.get("cellset") or []
            print(f"  [ventas_sri] fetch intento {attempt}: HTTP {r.status_code}")
        except requests.RequestException as exc:
            print(f"  [ventas_sri] fetch error: {exc}")
        if attempt < _RETRY:
            time.sleep(2 ** attempt)
    return None


# ---------------------------------------------------------------------------
# Parseo del cellset
# ---------------------------------------------------------------------------

def _parse_cellset(cellset: list, start_year: int) -> list[dict]:
    """
    Extrae registros del cellset Saiku.

    Estructura para CrossJoin(ANIO, ACTIVIDAD) ON ROWS con 1 medida ON COLUMNS:
      fila 0   : encabezados (ROW_HEADER_HEADER, COLUMN_HEADER)
      filas 1+ : [ROW_HEADER(anio|null), ROW_HEADER(codigo), DATA_CELL(valor)]

    Saiku hereda valores nulos de la fila anterior en los ROW_HEADER.
    """
    records = []
    if not cellset or len(cellset) < 2:
        return records

    last_anio_raw = None

    for row in cellset[1:]:
        if not row:
            continue

        row_hdrs   = [c for c in row if "HEADER" in c.get("type", "") and c.get("type") != "COLUMN_HEADER"]
        data_cells = [c for c in row if c.get("type") == "DATA_CELL"]

        if len(row_hdrs) < 2 or not data_cells:
            continue

        # Año: primer header — puede ser null (heredado)
        anio_val = row_hdrs[0].get("value")
        if anio_val and str(anio_val).lower() not in ("null", "none", ""):
            last_anio_raw = anio_val
        anio_raw = last_anio_raw

        # Parsear año
        try:
            anio = int(str(anio_raw).strip())
        except (ValueError, TypeError):
            continue

        if anio < start_year:
            continue

        # Codigo CIIU: ultimo header de la fila (el nivel mas especifico)
        codigo = str(row_hdrs[-1].get("value") or "").strip()
        if not codigo or codigo.lower() in ("null", "none", ""):
            continue

        # Valor: DATA_CELL (valor formateado con comas)
        raw_val = data_cells[0].get("value")
        try:
            valor = float(str(raw_val).replace(",", "")) if raw_val not in (None, "") else None
        except (ValueError, TypeError):
            valor = None

        records.append({
            "codigo_ciiu": codigo,
            "anio":        anio,
            "valor":       valor,
        })

    return records


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def fetch(start_year: int = FIRST_YEAR) -> dict:
    """
    Consulta Saiku API para las 6 metricas CIIU.

    Returns:
        dict[table_name -> list[dict(codigo_ciiu, anio, valor)]]
    """
    session = requests.Session()

    print("[ventas_sri] Autenticando en Saiku...")
    if not _login(session):
        print("[ventas_sri] Fallo de autenticacion.")
        return {m["table"]: [] for m in _METRICS}

    result: dict = {}
    for m in _METRICS:
        table = m["table"]
        print(f"[ventas_sri] Consultando {table} ({m['ds']}/{m['cube']})...")

        qid = _create_qm(session, m["ds"], m["cube"])
        if qid is None:
            print(f"[ventas_sri] No se pudo crear query para {table}.")
            result[table] = []
            time.sleep(_DELAY)
            continue

        mdx = _build_mdx(m)
        cellset = _fetch_cellset(session, qid, mdx)

        if cellset is None:
            print(f"[ventas_sri] Sin respuesta para {table}.")
            result[table] = []
        else:
            records = _parse_cellset(cellset, start_year)
            print(f"[ventas_sri] {table}: {len(records)} registros (>={start_year}).")
            result[table] = records

        # Borrar query del servidor (limpieza)
        try:
            session.delete(f"{_API}/query/{qid}", headers=_HEADERS, timeout=10)
        except Exception:
            pass

        time.sleep(_DELAY)

    return result
