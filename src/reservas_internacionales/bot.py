"""
Bot de descarga: Reservas Internacionales — BCE Ecuador

Portal: https://contenido.bce.fin.ec/documentos/informacioneconomica/
        MonetarioFinanciero/ix_ReservasInternacionales.html

Estrategia:
  - Navega al indice BCE para encontrar el link directo al Excel.
  - Si el archivo local ya existe y el tamano remoto coincide → salta.
  - Si no existe o el tamano difiere → descarga.

Archivo: ReservasInternacionales.xlsx (nombre fijo, actualizado mensualmente)
Destino: downloads/reservas_internacionales/ReservasInternacionales.xlsx
"""

import requests
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BCE_INDEX_URL = (
    "https://contenido.bce.fin.ec/documentos/informacioneconomica"
    "/MonetarioFinanciero/ix_ReservasInternacionales.html"
)

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "reservas_internacionales"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

DEST_FILE        = DOWNLOAD_DIR / "ReservasInternacionales.xlsx"
PAGE_TIMEOUT     = 60_000   # ms
DOWNLOAD_TIMEOUT = 120      # s

_FILENAME = "ReservasInternacionales.xlsx"


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def download_and_extract() -> dict:
    """
    Verifica y descarga el Excel de Reservas Internacionales si hay una
    version nueva. Retorna {'file': Path} o {'file': None} si fallo.
    """
    url = _find_download_url()
    if not url:
        print("[ri] No se encontro el link de descarga en el indice BCE.")
        return {"file": None}

    # Comparar tamano remoto vs local
    if DEST_FILE.exists():
        remote_size = _get_remote_size(url)
        local_size  = DEST_FILE.stat().st_size
        if remote_size and remote_size == local_size:
            print(f"[ri] [skip] Archivo ya actualizado ({local_size:,} bytes)")
            return {"file": DEST_FILE}
        print(f"[ri] Nueva version detectada (local={local_size:,}, remoto={remote_size})")

    print(f"[ri] Descargando {_FILENAME}...")
    if _download_file(url, DEST_FILE):
        return {"file": DEST_FILE}
    return {"file": None}


# ---------------------------------------------------------------------------
# Scraping del indice con Playwright
# ---------------------------------------------------------------------------

def _find_download_url() -> str | None:
    """Navega al indice BCE y retorna la URL directa al Excel."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page    = browser.new_page()

        try:
            page.goto(BCE_INDEX_URL, wait_until="networkidle", timeout=PAGE_TIMEOUT)
        except PWTimeout:
            print("[ri] [warn] Timeout networkidle — continuando con DOM parcial")

        # Buscar el link al Excel por nombre de archivo
        selector = f'a[href*="{_FILENAME}"]'
        elements = page.locator(selector).all()
        url = None
        if elements:
            url = elements[0].get_attribute("href") or None

        browser.close()

    if url:
        print(f"[ri] Link encontrado: {url}")
    return url


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_remote_size(url: str) -> int | None:
    try:
        resp = requests.head(url, timeout=15, allow_redirects=True)
        cl = resp.headers.get("Content-Length")
        return int(cl) if cl else None
    except Exception:
        return None


def _download_file(url: str, dest: Path) -> bool:
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
