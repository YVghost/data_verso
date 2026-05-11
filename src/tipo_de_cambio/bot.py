"""
Bot de descarga: Indice de Tipo de Cambio Real (ITCER) — BCE Ecuador

Pagina indice: https://contenido.bce.fin.ec/documentos/informacioneconomica/
               SectorExterno/ix_TipoCambioReal.html

Estrategia dinamica de URL:
  1. Hace GET a ix_TipoCambioReal.html y extrae todos los links que
     coincidan con IndicesTipoCambioReal-YYYY_100.xlsx.
  2. Selecciona el que tenga el anio base mas alto (el mas reciente).
     Esto cubre el caso en que BCE cambie de 2018=100 a 2025=100, etc.
  3. Si el archivo local ya existe y el tamano coincide con el remoto -> salta.
  4. Si el tamano difiere -> descarga la nueva version.

Archivo: IndicesTipoCambioReal-{AÑO_BASE}_100.xlsx
Destino: downloads/tipo_de_cambio/IndicesTipoCambioReal-{AÑO_BASE}_100.xlsx
"""

import json
import re
import requests
from pathlib import Path

BCE_INDEX_URL = (
    "https://contenido.bce.fin.ec/documentos/informacioneconomica"
    "/SectorExterno/ix_TipoCambioReal.html"
)
BCE_BASE_URL = "https://contenido.bce.fin.ec"
_FILE_PATTERN = re.compile(
    r'IndicesTipoCambioReal-(\d{4})_100\.xlsx', re.IGNORECASE
)

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "tipo_de_cambio"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT_GET      = 30   # segundos para requests HEAD/GET simples
TIMEOUT_DOWNLOAD = 120  # segundos para descarga del Excel


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def download_and_extract() -> dict:
    """
    Encuentra el Excel mas reciente en la pagina BCE y lo descarga si hay
    una version nueva (o si no existe localmente).

    Retorna {'file': Path} o {'file': None} si fallo.
    """
    url, year_base = _find_latest_url()
    if not url:
        print("[tc] No se encontro ningun link de Excel en la pagina BCE.")
        return {"file": None}

    print(f"[tc] Excel mas reciente: base {year_base}=100")
    print(f"[tc] URL: {url}")

    filename = url.rsplit("/", 1)[-1]
    dest     = DOWNLOAD_DIR / filename

    # Verificar si ya esta descargado y actualizado
    if dest.exists():
        remote_size = _get_remote_size(url)
        local_size  = dest.stat().st_size
        if remote_size and remote_size == local_size:
            print(f"[tc] [skip] Archivo ya actualizado: {filename} ({local_size:,} bytes)")
            return {"file": dest}
        print(f"[tc] Nueva version detectada (local={local_size:,}, remoto={remote_size})")
        # Borrar versiones antiguas con distinto anio base
        _cleanup_old_files(dest)

    print(f"[tc] Descargando {filename}...")
    if _download(url, dest):
        return {"file": dest}
    return {"file": None}


# ---------------------------------------------------------------------------
# Deteccion dinamica del link
# ---------------------------------------------------------------------------

def _find_latest_url() -> tuple[str | None, int | None]:
    """
    Hace GET a la pagina indice, extrae todos los links que coincidan
    con el patron IndicesTipoCambioReal-YYYY_100.xlsx y retorna
    (url_completa, anio_base) del mas reciente.
    """
    try:
        resp = requests.get(BCE_INDEX_URL, timeout=TIMEOUT_GET)
        resp.raise_for_status()
        html = resp.text
    except Exception as ex:
        print(f"[tc] Error al acceder a la pagina BCE: {ex}")
        return None, None

    matches = _FILE_PATTERN.findall(html)
    if not matches:
        print("[tc] No se encontraron archivos ITCER en la pagina.")
        return None, None

    # Seleccionar el anio base mas alto
    latest_year = max(int(y) for y in matches)
    filename    = f"IndicesTipoCambioReal-{latest_year}_100.xlsx"

    # Reconstruir URL completa desde el href del link
    href_pattern = re.compile(
        rf'href=["\']([^"\']*{re.escape(filename)})["\']', re.IGNORECASE
    )
    href_match = href_pattern.search(html)
    if href_match:
        href = href_match.group(1)
        url  = href if href.startswith("http") else BCE_BASE_URL + href
    else:
        # Fallback: construir URL por convencion
        url = (
            f"{BCE_BASE_URL}/documentos/informacioneconomica"
            f"/SectorExterno/{filename}"
        )

    return url, latest_year


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cleanup_old_files(new_dest: Path) -> None:
    """Elimina Excels ITCER con anio base distinto al nuevo."""
    for f in DOWNLOAD_DIR.glob("IndicesTipoCambioReal-*_100.xlsx"):
        if f != new_dest:
            print(f"[tc] Eliminando version antigua: {f.name}")
            f.unlink()


def _get_remote_size(url: str) -> int | None:
    try:
        resp = requests.head(url, timeout=TIMEOUT_GET, allow_redirects=True)
        cl = resp.headers.get("Content-Length")
        return int(cl) if cl else None
    except Exception:
        return None


def _download(url: str, dest: Path) -> bool:
    try:
        resp = requests.get(url, timeout=TIMEOUT_DOWNLOAD, stream=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        print(f"  Guardado: {dest.name} ({dest.stat().st_size:,} bytes)")
        return True
    except Exception as ex:
        print(f"  Error descargando {dest.name}: {ex}")
        if dest.exists():
            dest.unlink()
        return False
