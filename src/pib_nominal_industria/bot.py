"""
Bot de descarga: PIB Nominal Desagregado por Industria (VAB) — BCE Ecuador

Fuente: BCE Cuentas Nacionales Trimestrales
URL   : https://contenido.bce.fin.ec/documentos/informacioneconomica/
        cuentasnacionales/ix_cuentasnacionalestrimestrales.html

Descarga los archivos Excel "Valor agregado bruto por industrias" por trimestre.
  Trimestrales : vab_{cod}_{YYYYQQ}.xlsx   (QQ = 01..04)
  Preliminares : vab_{cod}_{YYYY}prel.xlsx

Excluye variantes por sector: vab_4g_* y vab_p_np_*

Sin Playwright — requests + regex sobre el HTML estatico.
Deteccion de cambios: ETag por archivo.
  - Historicos (< anio_actual - 1) : se omiten si ya existen en disco.
  - Recientes  (>= anio_actual - 1): se re-verifican con ETag siempre.
"""

import re
from datetime import datetime
from pathlib import Path

import requests

PAGE_URL = (
    "https://contenido.bce.fin.ec/documentos/informacioneconomica"
    "/cuentasnacionales/ix_cuentasnacionalestrimestrales.html"
)

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "pib_nominal_industria"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

FIRST_YEAR = 2023   # primer anio con archivos disponibles en la pagina BCE
TIMEOUT    = 60

# Captura href de archivos vab_<numero>_<periodo>.xlsx
# Excluye: vab_4g_ y vab_p_np_ por inclusion negativa del patron
_LINK_RE = re.compile(
    r'href=["\']([^"\']*?/vab_\d+_(\d{4}(?:\d{2}|prel))\.xlsx)["\']',
    re.IGNORECASE,
)

_HEADERS = {"User-Agent": "Mozilla/5.0"}


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def fetch(start_year: int = FIRST_YEAR) -> list[Path]:
    """
    Descarga los Excel VAB por industrias desde la pagina BCE.
    Retorna lista de rutas de archivos disponibles en disco.
    """
    print("[vab_industria] Obteniendo pagina BCE CNT...")
    html = _get_page()

    links = _parse_links(html, start_year)
    if not links:
        print("[vab_industria] No se encontraron archivos de descarga.")
        return []

    current_year = datetime.today().year
    files: list[Path] = []

    for fname, url, year in links:
        is_recent = (year >= current_year - 1)
        path = _download_file(fname, url, is_recent)
        if path:
            files.append(path)

    print(f"[vab_industria] {len(files)} archivos disponibles en disco.")
    return files


# ---------------------------------------------------------------------------
# Parsing de links
# ---------------------------------------------------------------------------

def _get_page() -> str:
    resp = requests.get(PAGE_URL, timeout=TIMEOUT, headers=_HEADERS)
    resp.raise_for_status()
    return resp.text


def _parse_links(html: str, start_year: int) -> list[tuple[str, str, int]]:
    """
    Extrae (filename, url, year) de todos los links VAB por industrias.
    Excluye vab_4g_ y vab_p_np_.
    """
    seen: set[str] = set()
    results: list[tuple[str, str, int]] = []

    for m in _LINK_RE.finditer(html):
        url    = m.group(1)
        period = m.group(2)   # "202501" o "2024prel"

        # Excluir variantes de agregacion
        if "4g_" in url or "p_np" in url:
            continue

        # Asegurar URL absoluta
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

    results.sort(key=lambda t: t[0])  # orden cronologico por nombre de archivo
    if results:
        years = sorted({r[2] for r in results})
        print(f"[vab_industria] {len(results)} archivos encontrados, anios: {years}")

    return results


# ---------------------------------------------------------------------------
# Descarga con ETag
# ---------------------------------------------------------------------------

def _download_file(fname: str, url: str, is_recent: bool) -> Path | None:
    dest      = DOWNLOAD_DIR / fname
    etag_path = DOWNLOAD_DIR / (fname + ".etag")

    # Historicos: omitir si ya existe en disco
    if dest.exists() and not is_recent:
        print(f"[vab_industria] {fname}: ya existe, omitiendo.")
        return dest

    meta = _get_remote_meta(url)
    if meta is None:
        if dest.exists():
            print(f"[vab_industria] {fname}: sin respuesta remota; usando local.")
            return dest
        print(f"[vab_industria] {fname}: no disponible, omitiendo.")
        return None

    remote_etag = meta["etag"] or meta["last_modified"]
    local_etag  = etag_path.read_text(encoding="utf-8").strip() if etag_path.exists() else ""

    if dest.exists() and remote_etag and local_etag == remote_etag:
        print(f"[vab_industria] {fname}: sin cambios (ETag coincide), omitiendo.")
        return dest

    print(f"[vab_industria] Descargando {fname}...")
    _stream_download(url, dest)
    if remote_etag:
        etag_path.write_text(remote_etag, encoding="utf-8")
    print(f"[vab_industria] {fname}: guardado.")
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
