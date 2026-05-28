"""
Bot de descarga: PIB Nominal — Oferta y Utilización de Bienes y Servicios (BCE)

Fuente: BCE Cuentas Nacionales Trimestrales
URL   : https://contenido.bce.fin.ec/documentos/informacioneconomica/
        cuentasnacionales/ix_cuentasnacionalestrimestrales.html

Archivos: tou_{cod}_{YYYYQQ}.xlsx  (QQ = 01..04)
          tou_{cod}_{YYYY}prel.xlsx (preliminares con código)
          tou_{YYYY}prel.xlsx       (preliminares sin código)

El número de código (131, 132, …) cambia en cada edición pero el
patrón del nombre permite descubrirlo dinámicamente desde el HTML.
Cada edición contiene datos desde 2000.I hasta el trimestre publicado.

Sin Playwright — requests + regex sobre el HTML estático.
Detección de cambios: ETag por archivo.
  - Históricos (< año_actual - 1): se omiten si ya existen en disco.
  - Recientes (>= año_actual - 1): se re-verifican con ETag siempre.
"""

import re
from datetime import datetime
from pathlib import Path

import requests

PAGE_URL = (
    "https://contenido.bce.fin.ec/documentos/informacioneconomica"
    "/cuentasnacionales/ix_cuentasnacionalestrimestrales.html"
)

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "pib_nominal_oferta"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

FIRST_YEAR = 2023   # primer año con ediciones disponibles en el HTML del BCE
TIMEOUT    = 60

# Captura href de archivos tou_*.xlsx en dos variantes:
#   tou_{cod}_{YYYYQQ}.xlsx     → period = YYYYQQ  (ej: 202504)
#   tou_{cod}_{YYYY}prel.xlsx   → period = YYYYprel
#   tou_{YYYY}prel.xlsx         → period = YYYYprel (sin código)
_LINK_RE = re.compile(
    r'href=["\']([^"\']*?/tou_(?:\d+_)?(\d{4}(?:\d{2}|prel))\.xlsx)["\']',
    re.IGNORECASE,
)

_HEADERS = {"User-Agent": "Mozilla/5.0"}


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def fetch(start_year: int = FIRST_YEAR) -> list[Path]:
    """
    Descarga los Excel tou_ desde la página BCE.
    Retorna lista de rutas de archivos disponibles en disco.
    """
    print("[pib_oferta] Obteniendo página BCE CNT...")
    html = _get_page()

    links = _parse_links(html, start_year)
    if not links:
        print("[pib_oferta] No se encontraron archivos tou_.")
        return []

    current_year = datetime.today().year
    files: list[Path] = []

    for fname, url, year in links:
        is_recent = (year >= current_year - 1)
        path = _download_file(fname, url, is_recent)
        if path:
            files.append(path)

    print(f"[pib_oferta] {len(files)} archivos disponibles en disco.")
    return files


# ---------------------------------------------------------------------------
# Parsing de links
# ---------------------------------------------------------------------------

def _get_page() -> str:
    resp = requests.get(PAGE_URL, timeout=TIMEOUT, headers=_HEADERS)
    resp.raise_for_status()
    return resp.text


def _parse_links(html: str, start_year: int) -> list[tuple[str, str, int]]:
    """Extrae (filename, url, year) de todos los links tou_."""
    seen: set[str] = set()
    results: list[tuple[str, str, int]] = []

    for m in _LINK_RE.finditer(html):
        url    = m.group(1)
        period = m.group(2)   # "202504" o "2025prel"

        if not url.startswith("http"):
            url = "https://contenido.bce.fin.ec" + url

        year = int(period[:4])
        if year < start_year:
            continue

        if url in seen:
            continue
        seen.add(url)

        fname = url.split("/")[-1]
        results.append((fname, url, year))

    results.sort(key=lambda t: t[0])
    if results:
        years = sorted({r[2] for r in results})
        print(f"[pib_oferta] {len(results)} archivos encontrados, años: {years}")

    return results


# ---------------------------------------------------------------------------
# Descarga con ETag
# ---------------------------------------------------------------------------

def _download_file(fname: str, url: str, is_recent: bool) -> Path | None:
    dest      = DOWNLOAD_DIR / fname
    etag_path = DOWNLOAD_DIR / (fname + ".etag")

    if dest.exists() and not is_recent:
        print(f"[pib_oferta] {fname}: ya existe, omitiendo.")
        return dest

    meta = _get_remote_meta(url)
    if meta is None:
        if dest.exists():
            print(f"[pib_oferta] {fname}: sin respuesta remota; usando local.")
            return dest
        print(f"[pib_oferta] {fname}: no disponible, omitiendo.")
        return None

    remote_etag = meta["etag"] or meta["last_modified"]
    local_etag  = etag_path.read_text(encoding="utf-8").strip() if etag_path.exists() else ""

    if dest.exists() and remote_etag and local_etag == remote_etag:
        print(f"[pib_oferta] {fname}: sin cambios (ETag coincide), omitiendo.")
        return dest

    print(f"[pib_oferta] Descargando {fname}...")
    _stream_download(url, dest)
    if remote_etag:
        etag_path.write_text(remote_etag, encoding="utf-8")
    print(f"[pib_oferta] {fname}: guardado.")
    return dest


def _get_remote_meta(url: str) -> dict | None:
    try:
        resp = requests.head(url, timeout=30, allow_redirects=True, headers=_HEADERS)
        if resp.status_code != 200:
            return None
        return {
            "etag":          resp.headers.get("ETag", ""),
            "last_modified": resp.headers.get("Last-Modified", ""),
        }
    except requests.RequestException:
        return None


def _stream_download(url: str, dest: Path) -> None:
    with requests.get(url, timeout=TIMEOUT, stream=True, headers=_HEADERS) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
