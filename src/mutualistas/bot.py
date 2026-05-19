"""
Bot de descarga: Captaciones Mutualistas — SEPS Ecuador

Fuente  : https://estadisticas.seps.gob.ec/index.php/estadisticas-sfps/
Seccion : Captaciones mensuales

Archivos descargados (ZIP):
  reportes/  — ZIP con 4 archivos xlsm/xlsx por año (Mut, S1, S2, S3)
  bases/     — ZIP con 1 archivo TXT por año (tab-separated)

Cobertura:
  Reportes : 2017-presente  (2017-2019 dentro del ZIP "años anteriores" id=908)
  Bases    : 2018-presente  (pre-2018 dentro del ZIP "años anteriores" id=914)

Deteccion de cambios: ETag almacenado en sidecar .etag.
Los download_id son estables en SEPS; se actualizan en este diccionario
cuando la SEPS publica un nuevo año (no se scrape dinamicamente para
evitar confundir secciones distintas de la pagina).
"""

from datetime import datetime
from pathlib import Path

import requests

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "mutualistas"
REPORTES_DIR = DOWNLOAD_DIR / "reportes"
BASES_DIR    = DOWNLOAD_DIR / "bases"
REPORTES_DIR.mkdir(parents=True, exist_ok=True)
BASES_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT    = 120
HEADERS    = {"User-Agent": "Mozilla/5.0"}
FIRST_YEAR = 2017

# ---------------------------------------------------------------------------
# URLs por año — actualizar aqui cuando SEPS publique un nuevo año
# Clave "anterior" = ZIP historico con multiples años
# ---------------------------------------------------------------------------

_REPORTES_URLS: dict[int | str, str] = {
    2026: "https://estadisticas.seps.gob.ec/?sdm_process_download=1&download_id=3263",
    2025: "https://estadisticas.seps.gob.ec/?sdm_process_download=1&download_id=2795",
    2024: "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=2365",
    2023: "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=1847",
    2022: "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=1133",
    2021: "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=906",
    2020: "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=907",
    "anterior": "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=908",
}

_BASES_URLS: dict[int | str, str] = {
    2026: "https://estadisticas.seps.gob.ec/?sdm_process_download=1&download_id=3268",
    2025: "https://estadisticas.seps.gob.ec/?sdm_process_download=1&download_id=2829",
    2024: "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=2360",
    2023: "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=1855",
    2022: "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=1169",
    2021: "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=910",
    2020: "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=911",
    2019: "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=912",
    2018: "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=913",
    "anterior": "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id=914",
}


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def fetch(start_year: int = FIRST_YEAR) -> dict:
    """
    Descarga ZIPs de reportes y bases desde start_year hasta el año actual.
    Retorna {"reportes": list[Path], "bases": list[Path]}.
    """
    current_year = datetime.today().year

    reportes_files: list[Path] = []
    bases_files:    list[Path] = []

    # --- Reportes ---
    # ZIP "anterior" cubre 2015-2019; descargar si necesitamos algun año pre-2020
    if start_year < 2020 and "anterior" in _REPORTES_URLS:
        p = _download_zip("anterior", _REPORTES_URLS["anterior"], REPORTES_DIR,
                          is_historic=True)
        if p:
            reportes_files.append(p)

    for year in range(max(start_year, 2020), current_year + 1):
        url = _REPORTES_URLS.get(year)
        if url:
            # Solo el anio actual puede actualizarse frecuentemente
            p = _download_zip(str(year), url, REPORTES_DIR,
                              is_historic=(year < current_year))
            if p:
                reportes_files.append(p)
        else:
            print(f"[mutualistas] reportes {year}: URL no registrada. "
                  f"Actualizar _REPORTES_URLS en bot.py.")

    # --- Bases ---
    if start_year < 2018 and "anterior" in _BASES_URLS:
        p = _download_zip("anterior", _BASES_URLS["anterior"], BASES_DIR,
                          is_historic=True)
        if p:
            bases_files.append(p)

    for year in range(max(start_year, 2018), current_year + 1):
        url = _BASES_URLS.get(year)
        if url:
            p = _download_zip(str(year), url, BASES_DIR,
                              is_historic=(year < current_year))
            if p:
                bases_files.append(p)
        else:
            print(f"[mutualistas] bases {year}: URL no registrada. "
                  f"Actualizar _BASES_URLS en bot.py.")

    print(f"[mutualistas] Reportes: {len(reportes_files)} ZIP(s)  "
          f"Bases: {len(bases_files)} ZIP(s)")
    return {"reportes": reportes_files, "bases": bases_files}


# ---------------------------------------------------------------------------
# Descarga con deteccion de cambios via ETag
# ---------------------------------------------------------------------------

def _download_zip(key: str, url: str, dest_dir: Path,
                  is_historic: bool) -> Path | None:
    dest      = dest_dir / f"{key}.zip"
    etag_path = dest_dir / f"{key}.etag"

    # Archivos historicos completos (no el anio actual): solo descarga una vez
    if is_historic and dest.exists():
        print(f"[mutualistas] {key}: historico en disco, omitiendo.")
        return dest

    # Verificar si el contenido cambio en el servidor
    meta = _get_remote_meta(url)
    if meta is None:
        if dest.exists():
            print(f"[mutualistas] {key}: sin respuesta HEAD; usando local.")
            return dest
        print(f"[mutualistas] {key}: no disponible en SEPS, omitiendo.")
        return None

    remote_etag = meta["etag"] or meta["last_modified"]
    local_etag  = (etag_path.read_text(encoding="utf-8").strip()
                   if etag_path.exists() else "")

    if dest.exists() and remote_etag and local_etag == remote_etag:
        print(f"[mutualistas] {key}: sin cambios (ETag coincide), omitiendo.")
        return dest

    size_mb = f"{meta['size'] / 1e6:.1f} MB" if meta.get("size") else "?"
    print(f"[mutualistas] {key}: descargando ({size_mb})...")
    _stream_download(url, dest)
    if remote_etag:
        etag_path.write_text(remote_etag, encoding="utf-8")
    print(f"[mutualistas] {key}: guardado -> {dest.name}")
    return dest


def _get_remote_meta(url: str) -> dict | None:
    try:
        resp = requests.head(url, timeout=30, allow_redirects=True,
                             headers=HEADERS)
        if resp.status_code != 200:
            return None
        return {
            "etag":          resp.headers.get("ETag", ""),
            "last_modified": resp.headers.get("Last-Modified", ""),
            "size":          (int(resp.headers["Content-Length"])
                              if "Content-Length" in resp.headers else None),
        }
    except requests.RequestException:
        return None


def _stream_download(url: str, dest: Path) -> None:
    with requests.get(url, timeout=TIMEOUT, stream=True,
                      headers=HEADERS) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
