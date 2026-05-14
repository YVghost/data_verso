"""
Bot de descarga: Recaudacion Mensual SRI Ecuador

URL base : https://descargas.sri.gob.ec/download/datosAbiertos/sri_recaudacion_{YEAR}.csv
Cobertura: 2017 al anio actual
Sin Playwright - descarga directa con requests.

Deteccion de cambios: ETag (o Last-Modified si no hay ETag) almacenado en un
archivo sidecar .etag junto a cada CSV. Al re-ejecutar, si el ETag coincide
con el remoto el archivo se omite sin descargarlo.

Logica:
  - Anios historicos (< anio actual): omite si el archivo ya existe en disco.
  - Anio actual: re-descarga solo si el ETag remoto difiere del almacenado.
"""

from datetime import datetime
from pathlib import Path

import requests

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "recaudacion_mensual"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

FIRST_YEAR = 2017
BASE_URL   = "https://descargas.sri.gob.ec/download/datosAbiertos/sri_recaudacion_{year}.csv"
TIMEOUT    = 120


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def fetch(start_year: int = FIRST_YEAR) -> list[Path]:
    """
    Descarga archivos CSV del SRI desde start_year hasta el anio actual.
    Retorna lista de rutas a los archivos disponibles en disco.
    """
    current_year = datetime.today().year
    files: list[Path] = []

    for year in range(start_year, current_year + 1):
        path = _download_year(year, is_current=(year == current_year))
        if path:
            files.append(path)

    return files


# ---------------------------------------------------------------------------
# Descarga por anio
# ---------------------------------------------------------------------------

def _download_year(year: int, is_current: bool) -> Path | None:
    dest = DOWNLOAD_DIR / f"sri_recaudacion_{year}.csv"
    url  = BASE_URL.format(year=year)

    # Anios historicos: omitir si ya existe en disco
    if dest.exists() and not is_current:
        print(f"[recaudacion] {year}: ya existe, omitiendo.")
        return dest

    # Consultar metadatos remotos
    meta = _get_remote_meta(url)

    if meta is None:
        if dest.exists():
            print(f"[recaudacion] {year}: sin respuesta; usando archivo local.")
            return dest
        print(f"[recaudacion] {year}: no disponible en SRI, omitiendo.")
        return None

    # Comparar con ETag almacenado localmente
    etag_path   = DOWNLOAD_DIR / f"sri_recaudacion_{year}.etag"
    remote_etag = meta["etag"] or meta["last_modified"]
    local_etag  = etag_path.read_text(encoding="utf-8").strip() if etag_path.exists() else ""

    if dest.exists() and remote_etag and local_etag == remote_etag:
        print(f"[recaudacion] {year}: sin cambios (ETag coincide), omitiendo.")
        return dest

    # Descargar
    print(f"[recaudacion] {year}: descargando...")
    _stream_download(url, dest)
    if remote_etag:
        etag_path.write_text(remote_etag, encoding="utf-8")
    print(f"[recaudacion] {year}: guardado -> {dest.name}")
    return dest


def _get_remote_meta(url: str) -> dict | None:
    try:
        resp = requests.head(url, timeout=30, allow_redirects=True)
        if resp.status_code != 200:
            return None
        return {
            "etag":          resp.headers.get("ETag", ""),
            "last_modified": resp.headers.get("Last-Modified", ""),
        }
    except requests.RequestException:
        return None


def _stream_download(url: str, dest: Path) -> None:
    with requests.get(url, timeout=TIMEOUT, stream=True) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):  # 1 MB
                f.write(chunk)