"""
Bot de descarga: Información Monetaria Semanal — BCE Ecuador

Portal: https://contenido.bce.fin.ec/documentos/informacioneconomica/
        MonetarioFinanciero/ix_ReportesMonetarios.html

Estrategia de descarga:
  - Navega directamente al índice de BMS (iframe del portal), que expone
    TODOS los links de 2012 a hoy en una sola página.
  - Años históricos (2012 → año_actual-1): descarga SOLO la última semana
    disponible de cada año. Si ya existe un archivo en disco → salta.
  - Año actual: siempre verifica la semana más reciente; si la fecha del
    archivo en disco es igual a la disponible → salta; si hay una más
    nueva → descarga.

Patrones de nombre de archivo (ambos formatos en el mismo índice):
  Antiguo : InfMonetariaSemanal_DDMMYYYY.xls  (hasta ~2023)
  Nuevo   : BMS_DDMMYYYY.xlsx                 (desde ~2024)

Estructura de descarga:
  downloads/depositos_gobierno_bce/{YYYY}/{filename}
"""

import re
import requests
from datetime import date, datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# Índice único con todos los links (xls + xlsx, 2012-presente)
BMS_INDEX_URL = (
    "https://contenido.bce.fin.ec/documentos/informacioneconomica"
    "/MonetarioFinanciero/indice_BMS.htm"
)

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "depositos_gobierno_bce"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

START_YEAR       = 2012
PAGE_TIMEOUT     = 60_000   # ms
DOWNLOAD_TIMEOUT = 120      # s

# Captura DD, MM, YYYY del nombre de archivo (ambos formatos)
_FILE_URL_RE = re.compile(
    r"(?:InfMonetariaSemanal|BMS)_(\d{2})(\d{2})(\d{4})\.(xls|xlsx)$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def download_and_extract() -> dict:
    """
    Descarga la última semana de cada año (START_YEAR → actual).
    Retorna {'files': [Path, ...]}.
    """
    links_by_year = _scrape_index()
    if not links_by_year:
        print("[bce] No se encontraron links en el índice.")
        return {"files": []}

    current_year = datetime.today().year
    files = []

    for year in sorted(links_by_year):
        if year < START_YEAR:
            continue

        year_links = sorted(links_by_year[year], key=lambda x: x[0])
        if not year_links:
            continue

        latest_date, latest_url = year_links[-1]   # semana más reciente del año

        existing = _find_existing_file(year)

        # Año histórico ya descargado → saltar
        if existing and year < current_year:
            print(f"[bce] [skip] {year}: ya descargado ({existing.name})")
            files.append(existing)
            continue

        # Año actual: comparar fecha
        if existing and year == current_year:
            existing_date = _date_from_filename(existing.name)
            if existing_date and existing_date >= latest_date:
                print(f"[bce] [skip] {year}: última semana ya en disco ({existing.name})")
                files.append(existing)
                continue
            print(f"[bce] {year}: semana más nueva disponible ({latest_date})")

        # Descargar
        dest_dir = DOWNLOAD_DIR / str(year)
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = latest_url.rsplit("/", 1)[-1]
        dest = dest_dir / filename

        if dest.exists():
            print(f"[bce] [skip] Archivo ya existe: {filename}")
            files.append(dest)
            continue

        print(f"[bce] Descargando {year}: {filename}  ({latest_date})")
        if _download_file(latest_url, dest):
            files.append(dest)

    return {"files": files}


# ---------------------------------------------------------------------------
# Scraping del índice con Playwright
# ---------------------------------------------------------------------------

def _scrape_index() -> dict:
    """
    Navega directamente al índice BMS (que contiene TODOS los links de
    2012 a la fecha) y retorna {year: [(date, url), ...]}.
    """
    results: dict[int, list] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page    = browser.new_page()

        try:
            page.goto(BMS_INDEX_URL, wait_until="networkidle", timeout=PAGE_TIMEOUT)
        except PWTimeout:
            print("[bce] [warn] Timeout networkidle — continuando con DOM parcial")

        _collect_links(page, results)
        browser.close()

    found_years = sorted(y for y in results if y >= START_YEAR)
    total_links = sum(len(v) for v in results.values())
    print(f"[bce] Links encontrados: {total_links} en años {found_years}")
    return results


def _collect_links(page, results: dict) -> None:
    """Extrae hrefs de archivos IMS/BMS del DOM y los agrupa por año."""
    selector = 'a[href*="InfMonetariaSemanal"], a[href*="BMS_"]'
    elements = page.locator(selector).all()
    for el in elements:
        href = el.get_attribute("href") or ""
        parsed = _parse_file_url(href)
        if parsed:
            d, year = parsed
            bucket = results.setdefault(year, [])
            if not any(u == href for _, u in bucket):
                bucket.append((d, href))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_file_url(href: str):
    """
    'https://.../BMS_09012026.xlsx' → (date(2026,1,9), 2026)
    'https://.../InfMonetariaSemanal_30092012.xls' → (date(2012,9,30), 2012)
    Retorna None si no coincide.
    """
    m = _FILE_URL_RE.search(href)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(year, month, day), year
    except ValueError:
        return None


def _find_existing_file(year: int) -> Path | None:
    """Retorna el primer .xls/.xlsx que encuentre en downloads/{year}/."""
    year_dir = DOWNLOAD_DIR / str(year)
    if not year_dir.exists():
        return None
    for f in sorted(year_dir.glob("*.xls*"), reverse=True):
        if not f.name.startswith("~"):
            return f
    return None


def _date_from_filename(name: str) -> date | None:
    """Extrae la fecha del nombre del archivo."""
    m = _FILE_URL_RE.search(name)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
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
