"""
Bot de descarga: Índice de Precios al Consumidor (IPC) — INEC

Flujo:
  1. Construye la URL del ZIP probando meses desde el actual hacia atrás con
     HEAD requests (sin Playwright), usando el patrón conocido del INEC.
  2. Descarga el ZIP con requests (enlace público).
  3. Dentro del ZIP busca el archivo "SERIE HISTORICA IPC_*.xls".
  4. Extrae ese XLS bajo:
       downloads/inflacion_ecuador/{YYYYMM}/SERIE HISTORICA IPC_{MM}_{YYYY}.xls

URL del ZIP:
  .../web-inec/Inflacion/{YEAR}/{month_es}/Tabulados_y_series_historicas_Excel.zip
Nombre del XLS dentro del ZIP:
  SERIE HISTORICA IPC_{MM}_{YYYY}.xls  (p.ej. SERIE HISTORICA IPC_03_2026.xls)
"""

import re
import zipfile
import requests
from datetime import date
from pathlib import Path

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "inflacion_ecuador"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

_ZIP_BASE_URL = (
    "https://www.ecuadorencifras.gob.ec/documentos/web-inec"
    "/Inflacion/{year}/{month}/Tabulados_y_series_historicas_Excel.zip"
)
_MES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


DOWNLOAD_TIMEOUT  = 120   # segundos (requests GET)
HEAD_TIMEOUT      = 10    # segundos (requests HEAD probe)
MONTHS_LOOKBACK   = 13    # cuántos meses hacia atrás intentar


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def download_and_extract() -> dict:
    """
    Descarga el ZIP de series históricas IPC y extrae todos los XLS relevantes:
      - SERIE HISTORICA IPC_*.xls
      - ipc_indicadores_descriptivos_*.xls  (subcarpeta "Indicadores Descriptivos")
    Retorna {'xls_paths': [Path]}.
    """
    url = _find_zip_url()
    if not url:
        print("[inflacion] ERROR: no se encontró el enlace al ZIP en el portal.")
        return {"xls_paths": []}

    print(f"[inflacion] ZIP encontrado: {url}")

    yyyymm = _yyyymm_from_url(url)
    dest_dir = DOWNLOAD_DIR / (yyyymm or "latest")
    dest_dir.mkdir(parents=True, exist_ok=True)

    zip_name = url.rsplit("/", 1)[-1]
    zip_path = dest_dir / zip_name

    if zip_path.exists():
        print(f"[inflacion] [skip] ZIP ya existe: {zip_name}")
    else:
        print(f"[inflacion] Descargando: {zip_name}")
        if not _download_zip(url, zip_path):
            return {"xls_paths": []}

    xls_paths = _extract_serie_historica(zip_path, dest_dir)
    print(f"[inflacion] XLS disponible: {[p.name for p in xls_paths]}")
    return {"xls_paths": xls_paths}


# ---------------------------------------------------------------------------
# Búsqueda del enlace ZIP en el portal
# ---------------------------------------------------------------------------

def _find_zip_url() -> str:
    """
    Prueba URLs del patrón conocido del INEC desde el mes actual hacia atrás,
    verificando con HEAD requests cuál existe. No requiere Playwright.
    """
    today = date.today()
    year, month = today.year, today.month

    for _ in range(MONTHS_LOOKBACK):
        url = _ZIP_BASE_URL.format(year=year, month=_MES_ES[month])
        try:
            resp = requests.head(url, timeout=HEAD_TIMEOUT, allow_redirects=True)
            if resp.status_code == 200:
                print(f"[inflacion] ZIP encontrado: {url}")
                return url
            print(f"[inflacion] [probe] {_MES_ES[month]} {year} → HTTP {resp.status_code}")
        except Exception as ex:
            print(f"[inflacion] [probe] {_MES_ES[month]} {year} → error: {ex}")

        month -= 1
        if month == 0:
            month = 12
            year -= 1

    return ""


# ---------------------------------------------------------------------------
# Descarga del ZIP
# ---------------------------------------------------------------------------

def _download_zip(url: str, dest: Path) -> bool:
    try:
        resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        print(f"  Guardado: {dest.name} ({dest.stat().st_size:,} bytes)")
        return True
    except Exception as ex:
        print(f"  Error descargando {dest.name}: {ex}")
        if dest.exists():
            dest.unlink()
        return False


# ---------------------------------------------------------------------------
# Extracción del XLS de serie histórica
# ---------------------------------------------------------------------------

def _extract_serie_historica(zip_path: Path, dest_dir: Path) -> list:
    """
    Extrae todos los XLS del ZIP a dest_dir (plano, sin subcarpetas).
    El loader identifica cada archivo por su nombre.
    """
    extracted = []
    if not zip_path.exists():
        return extracted

    with zipfile.ZipFile(zip_path, "r") as z:
        members = z.namelist()
        xls_members = [m for m in members if re.search(r"\.(xls|xlsx)$", m, re.IGNORECASE)]
        print(f"  Archivos en ZIP: {[Path(m).name for m in xls_members]}")

        for member in xls_members:
            flat_name = Path(member).name
            if not flat_name:
                continue
            dest_path = dest_dir / flat_name
            if not dest_path.exists():
                dest_path.write_bytes(z.read(member))
                print(f"  Extraído: {flat_name}")
            extracted.append(dest_path)

    return extracted


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _yyyymm_from_url(url: str) -> str:
    """'.../Inflacion/2026/marzo/...' → '202603'"""
    _MES_NUM = {v: f"{k:02d}" for k, v in _MES_ES.items()}
    m = re.search(r"/Inflacion/(\d{4})/(\w+)/", url, re.IGNORECASE)
    if m:
        year  = m.group(1)
        month = _MES_NUM.get(m.group(2).lower(), "00")
        return f"{year}{month}"
    return ""
