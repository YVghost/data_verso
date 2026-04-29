"""
Bot de descarga: ENEMDU — Tabulados Mercado Laboral (trimestral + mensual)
INEC

Fuentes:
  Trimestral: https://www.ecuadorencifras.gob.ec/enemdu-trimestral/
  Mensual:    https://www.ecuadorencifras.gob.ec/estadisticas-laborales-enemdu/

Flujo (trimestral):
  ZIP descargado contiene todos los trimestres desde 2020 en 8 CSVs.
  Extrae bajo:  downloads/empleo/{año}/{trimestre}/   e.g. 2026/I/

Flujo (mensual):
  ZIP descargado contiene todos los meses desde 2007 en los mismos 8 CSVs.
  Extrae bajo:  downloads/empleo/{año}/{YYYYMM}/       e.g. 2026/202603/

Ambos flujos eliminan automáticamente archivos de índice y glosario.

URL patterns:
  Trimestral: .../EMPLEO/{YEAR}/Trimestre_{Q}/{YEAR}_{Q}_trimestre_Tabulados_Mercado_Laboral_CSV.zip
  Mensual:    .../EMPLEO/{YEAR}/{MonthName}_{YEAR}/{YYYYMM}_Tabulados_Mercado_Laboral_CSV.zip
"""

import re
import zipfile
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

PORTAL_TRIMESTRAL_URL = "https://www.ecuadorencifras.gob.ec/enemdu-trimestral/"
PORTAL_MENSUAL_URL    = "https://www.ecuadorencifras.gob.ec/estadisticas-laborales-enemdu/"

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "empleo"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

_ZIP_SELECTOR = 'a[href*="Tabulados_Mercado_Laboral_CSV"]'

# Trimestral: extrae (year, quarter) del path de la URL
_TRIMESTRAL_URL_RE = re.compile(
    r"/EMPLEO/(\d{4})/Trimestre_([IVXivx]+)/",
    re.IGNORECASE,
)

# Mensual: extrae YYYYMM del nombre del archivo ZIP
_MENSUAL_URL_RE = re.compile(
    r"/(\d{4})(\d{2})_Tabulados_Mercado_Laboral_CSV\.zip",
    re.IGNORECASE,
)

_SKIP_WORDS    = ("indice", "índice", "glosario")
_QUARTER_ORDER = {"I": 1, "II": 2, "III": 3, "IV": 4}

DOWNLOAD_TIMEOUT = 120    # segundos (requests)
PAGE_TIMEOUT     = 60_000 # ms (Playwright)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def download_and_extract() -> dict:
    """Descarga ZIPs trimestrales de ENEMDU. Retorna {'csvs': [Path, ...]}."""
    links = _collect_links(PORTAL_TRIMESTRAL_URL, _parse_trimestral_link)
    print(f"[empleo] Trimestral — períodos encontrados: {len(links)}")
    return _download_links(links, folder_fn=lambda year, key: DOWNLOAD_DIR / str(year) / key)


def download_and_extract_monthly() -> dict:
    """Descarga ZIPs mensuales de ENEMDU. Retorna {'csvs': [Path, ...]}."""
    links = _collect_links(PORTAL_MENSUAL_URL, _parse_mensual_link)
    print(f"[empleo] Mensual — períodos encontrados: {len(links)}")
    return _download_links(links, folder_fn=lambda year, key: DOWNLOAD_DIR / str(year) / key)


# ---------------------------------------------------------------------------
# Recolección de links
# ---------------------------------------------------------------------------

def _collect_links(portal_url: str, parse_fn) -> list:
    """
    Carga la página con Playwright y extrae hrefs de ZIPs Tabulados CSV.
    parse_fn(href) → (url, year, key) o None.
    Retorna lista ordenada cronológicamente.
    """
    links = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page    = browser.new_page()
        try:
            page.goto(portal_url, wait_until="networkidle", timeout=PAGE_TIMEOUT)
        except PWTimeout:
            print("[empleo] [warn] Timeout en networkidle — continuando con DOM parcial")

        elements = page.locator(_ZIP_SELECTOR).all()
        hrefs    = [el.get_attribute("href") or "" for el in elements]
        browser.close()

    print(f"[empleo] Links CSV encontrados en {portal_url}: {len(hrefs)}")

    for href in hrefs:
        if not href:
            continue
        parsed = parse_fn(href)
        if parsed is None:
            print(f"[empleo] [warn] No se pudo parsear link: {href}")
            continue
        links.append(parsed)

    links.sort(key=lambda x: (x[1], x[2]))  # ordenar por (year, key)
    return links


def _parse_trimestral_link(href: str):
    """Extrae (url, year, quarter) de un href trimestral."""
    m = _TRIMESTRAL_URL_RE.search(href)
    if not m:
        return None
    year    = int(m.group(1))
    quarter = m.group(2).upper()
    return (href, year, quarter)


def _parse_mensual_link(href: str):
    """Extrae (url, year, yyyymm) de un href mensual."""
    m = _MENSUAL_URL_RE.search(href)
    if not m:
        return None
    year   = int(m.group(1))
    yyyymm = m.group(1) + m.group(2)  # e.g. "202603"
    return (href, year, yyyymm)


# ---------------------------------------------------------------------------
# Descarga y extracción
# ---------------------------------------------------------------------------

def _download_links(links: list, folder_fn) -> dict:
    """
    Para cada (url, year, key) en links:
      - crea la carpeta folder_fn(year, key)
      - descarga el ZIP si no existe
      - extrae los CSVs útiles
    Retorna {'csvs': [Path, ...]}.
    """
    result = {"csvs": []}

    for url, year, key in links:
        dest_dir = folder_fn(year, key)
        dest_dir.mkdir(parents=True, exist_ok=True)

        zip_name = url.rsplit("/", 1)[-1]
        zip_path = dest_dir / zip_name

        if zip_path.exists():
            print(f"[empleo] [skip] Ya existe: {zip_name}")
        else:
            print(f"[empleo] Descargando: {zip_name}")
            _download_zip(url, zip_path)

        if zip_path.exists():
            result["csvs"].extend(_extract_csvs(zip_path, dest_dir))

    print(f"[empleo] Total CSVs disponibles: {len(result['csvs'])}")
    return result


def _download_zip(url: str, dest: Path) -> bool:
    """Descarga un ZIP público con requests. Retorna True si tuvo éxito."""
    try:
        resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        print(f"  ✓ Guardado: {dest.name} ({dest.stat().st_size:,} bytes)")
        return True
    except Exception as ex:
        print(f"  ✗ Error descargando {dest.name}: {ex}")
        if dest.exists():
            dest.unlink()
        return False


def _extract_csvs(zip_path: Path, dest_dir: Path) -> list:
    """
    Extrae todos los CSVs del ZIP en dest_dir.
    Omite archivos de índice y glosario.
    Retorna lista de Paths de CSVs útiles.
    """
    useful = []
    if not zip_path.exists():
        return useful

    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.namelist():
            if not re.search(r"\.csv$", member, re.IGNORECASE):
                continue

            flat_name = Path(member).name
            if _should_skip(flat_name):
                print(f"  [skip] {flat_name}")
                continue

            dest_path = dest_dir / flat_name
            if not dest_path.exists():
                dest_path.write_bytes(z.read(member))
                print(f"  Extraído: {flat_name}")

            useful.append(dest_path)

    return useful


def _should_skip(filename: str) -> bool:
    """True si el archivo es índice o glosario."""
    fn = filename.lower()
    return any(word in fn for word in _SKIP_WORDS)
