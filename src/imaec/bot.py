"""
Bot de descarga: IMAEc — Índice de Actividad Económica Coyuntural (BCE)

Fuente: BCE Cuentas Nacionales
URL   : https://contenido.bce.fin.ec/documentos/informacioneconomica/
        cuentasnacionales/ix_IMAEC.html

Patrón de archivo: IMAEc_{YYYYMM}.xlsx  (ej: IMAEc_202603.xlsx = Marzo 2026)
Frecuencia       : Mensual — nuevo archivo cada mes con nuevo nombre de URL.

El bot escanea el HTML de la página para descubrir el link vigente, lo
compara con el archivo local via ETag y descarga solo si hay cambios.
"""

import re
from pathlib import Path

import requests

PAGE_URL = (
    "https://contenido.bce.fin.ec/documentos/informacioneconomica"
    "/cuentasnacionales/ix_IMAEC.html"
)

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "imaec"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT  = 60
_HEADERS = {"User-Agent": "Mozilla/5.0"}

# Captura href de archivos IMAEc_YYYYMM.xlsx
_LINK_RE = re.compile(
    r'href=["\']([^"\']*?IMAEc_(\d{6})\.xlsx)["\']',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def fetch() -> list[Path]:
    """
    Descubre y descarga el/los archivos IMAEc desde la página BCE.
    Retorna lista de rutas disponibles en disco.
    """
    print("[imaec] Obteniendo página BCE IMAEc...")
    html = _get_page()

    links = _parse_links(html)
    if not links:
        print("[imaec] No se encontraron archivos IMAEc en la página.")
        return []

    files: list[Path] = []
    for fname, url in links:
        path = _download_file(fname, url)
        if path:
            files.append(path)

    print(f"[imaec] {len(files)} archivo(s) disponibles en disco.")
    return files


# ---------------------------------------------------------------------------
# Parsing de links
# ---------------------------------------------------------------------------

def _get_page() -> str:
    resp = requests.get(PAGE_URL, timeout=TIMEOUT, headers=_HEADERS)
    resp.raise_for_status()
    return resp.text


def _parse_links(html: str) -> list[tuple[str, str]]:
    """Extrae (filename, url) de todos los links IMAEc_YYYYMM.xlsx."""
    seen: set[str] = set()
    results: list[tuple[str, str]] = []

    for m in _LINK_RE.finditer(html):
        url    = m.group(1)
        period = m.group(2)   # "202603"

        if not url.startswith("http"):
            url = "https://contenido.bce.fin.ec" + url

        if url in seen:
            continue
        seen.add(url)

        fname = url.split("/")[-1]
        results.append((fname, url))
        print(f"[imaec] Encontrado: {fname}  ({period[:4]}-{period[4:]})")

    return results


# ---------------------------------------------------------------------------
# Descarga con ETag
# ---------------------------------------------------------------------------

def _download_file(fname: str, url: str) -> Path | None:
    dest      = DOWNLOAD_DIR / fname
    etag_path = DOWNLOAD_DIR / (fname + ".etag")

    meta = _get_remote_meta(url)
    if meta is None:
        if dest.exists():
            print(f"[imaec] {fname}: sin respuesta remota; usando local.")
            return dest
        print(f"[imaec] {fname}: no disponible, omitiendo.")
        return None

    remote_etag = meta["etag"] or meta["last_modified"]
    local_etag  = etag_path.read_text(encoding="utf-8").strip() if etag_path.exists() else ""

    if dest.exists() and remote_etag and local_etag == remote_etag:
        print(f"[imaec] {fname}: sin cambios (ETag coincide), omitiendo.")
        return dest

    size_mb = f"{meta['size'] / 1e6:.1f} MB" if meta.get("size") else "?"
    print(f"[imaec] Descargando {fname} ({size_mb})...")
    _stream_download(url, dest)
    if remote_etag:
        etag_path.write_text(remote_etag, encoding="utf-8")
    print(f"[imaec] {fname}: guardado.")
    return dest


def _get_remote_meta(url: str) -> dict | None:
    try:
        resp = requests.head(url, timeout=30, allow_redirects=True, headers=_HEADERS)
        if resp.status_code != 200:
            return None
        return {
            "etag":          resp.headers.get("ETag", ""),
            "last_modified": resp.headers.get("Last-Modified", ""),
            "size":          int(resp.headers["Content-Length"])
                             if "Content-Length" in resp.headers else None,
        }
    except requests.RequestException:
        return None


def _stream_download(url: str, dest: Path) -> None:
    with requests.get(url, timeout=TIMEOUT, stream=True, headers=_HEADERS) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
