"""
Bot de descarga: Colocaciones Mutualistas — SEPS Ecuador
Fuente: https://estadisticas.seps.gob.ec/index.php/estadisticas-sfps/#cartera_credito

5 tipos de descarga (un ZIP por año):
  volumen       Volumen de crédito mensual  (xlsm: Mut + S1/S2/S3)
  colocaciones  Colocaciones mensuales      (xlsm: Mut + S1/S2/S3)
  volumen_bruto Volumen de crédito bruto    (TXT tab-sep)
  col_bruto     Colocaciones mensual bruto  (TXT Deflate64, ~2.8 GB)
  tarjetas      Tarjetas mensuales          (2 TXT: con/sin forma de pago)

Cobertura individual por tipo:
  volumen       2020-presente  (pre-2020 en ZIP "anterior" id=1021)
  colocaciones  2020-presente  (pre-2020 en ZIP "anterior" id=1027)
  volumen_bruto 2018-presente  (pre-2018 en ZIP "anterior" id=1085)
  col_bruto     2017-presente  (pre-2017 en ZIP "anterior" id=1208)
  tarjetas      2018-presente  (pre-2018 en ZIP "anterior" id=1044)
"""

from datetime import datetime
from pathlib import Path

import requests

DOWNLOAD_DIR      = Path(__file__).resolve().parents[2] / "downloads" / "mutualistas" / "colocaciones"
VOLUMEN_DIR       = DOWNLOAD_DIR / "volumen"
COLOCACIONES_DIR  = DOWNLOAD_DIR / "col"
VOLUMEN_BRUTO_DIR = DOWNLOAD_DIR / "volumen_bruto"
COL_BRUTO_DIR     = DOWNLOAD_DIR / "col_bruto"
TARJETAS_DIR      = DOWNLOAD_DIR / "tarjetas"

for _d in [VOLUMEN_DIR, COLOCACIONES_DIR, VOLUMEN_BRUTO_DIR, COL_BRUTO_DIR, TARJETAS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

TIMEOUT    = 300
HEADERS    = {"User-Agent": "Mozilla/5.0"}
FIRST_YEAR = 2017

_SDM = "https://estadisticas.seps.gob.ec/?sdm_process_download=1&download_id="
_SMD = "https://estadisticas.seps.gob.ec/?smd_process_download=1&download_id="

# ---------------------------------------------------------------------------
# Volumen de crédito mensual (reportes xlsm)   — individual desde 2020
# ---------------------------------------------------------------------------
_VOLUMEN_URLS: dict[int | str, str] = {
    2026:       _SDM + "3271",
    2025:       _SDM + "2816",
    2024:       _SMD + "2343",
    2023:       _SMD + "1836",
    2022:       _SMD + "1111",
    2021:       _SMD + "1017",
    2020:       _SMD + "1019",
    "anterior": _SMD + "1021",   # cubre años pre-2020
}

# ---------------------------------------------------------------------------
# Colocaciones mensuales (reportes xlsm)        — individual desde 2020
# ---------------------------------------------------------------------------
_COL_URLS: dict[int | str, str] = {
    2026:       _SDM + "3274",
    2025:       _SDM + "2799",
    2024:       _SMD + "2370",
    2023:       _SMD + "1830",
    2022:       _SMD + "1129",
    2021:       _SMD + "1023",
    2020:       _SMD + "1025",
    "anterior": _SMD + "1027",   # cubre años pre-2020
}

# ---------------------------------------------------------------------------
# Volumen de crédito mensual (bases TXT)        — individual desde 2018
# ---------------------------------------------------------------------------
_VOLUMEN_BRUTO_URLS: dict[int | str, str] = {
    2026:       _SDM + "3277",
    2025:       _SDM + "2837",
    2024:       _SMD + "2346",
    2023:       _SMD + "1866",
    2022:       _SMD + "1143",
    2021:       _SMD + "1068",
    2020:       _SMD + "1075",
    2019:       _SMD + "1080",
    2018:       _SMD + "1082",
    "anterior": _SMD + "1085",   # cubre años pre-2018
}

# ---------------------------------------------------------------------------
# Colocaciones mensuales (bases TXT Deflate64)  — individual desde 2017
# ---------------------------------------------------------------------------
_COL_BRUTO_URLS: dict[int | str, str] = {
    2026:       _SDM + "3284",
    2025:       _SDM + "2802",
    2024:       _SMD + "2374",
    2023:       _SMD + "1861",
    2022:       _SMD + "1193",
    2021:       _SMD + "1198",
    2020:       _SMD + "1200",
    2019:       _SMD + "1202",
    2018:       _SMD + "1204",
    2017:       _SMD + "1206",
    "anterior": _SMD + "1208",   # cubre años pre-2017
}

# ---------------------------------------------------------------------------
# Tarjetas de crédito mensual                   — individual desde 2018
# ---------------------------------------------------------------------------
_TARJETAS_URLS: dict[int | str, str] = {
    2026:       _SDM + "3281",
    2025:       _SDM + "2790",
    2024:       _SMD + "2337",
    2023:       _SMD + "1871",
    2022:       _SMD + "1116",
    2021:       _SMD + "1035",
    2020:       _SMD + "1038",
    2019:       _SMD + "1040",
    2018:       _SMD + "1042",
    "anterior": _SMD + "1044",   # cubre años pre-2018
}

# año mínimo individual por tipo (por debajo → usar "anterior")
_EARLIEST = {
    "volumen":       2020,
    "colocaciones":  2020,
    "volumen_bruto": 2018,
    "col_bruto":     2017,
    "tarjetas":      2018,
}

_URL_MAP = {
    "volumen":       _VOLUMEN_URLS,
    "colocaciones":  _COL_URLS,
    "volumen_bruto": _VOLUMEN_BRUTO_URLS,
    "col_bruto":     _COL_BRUTO_URLS,
    "tarjetas":      _TARJETAS_URLS,
}

_DIR_MAP = {
    "volumen":       VOLUMEN_DIR,
    "colocaciones":  COLOCACIONES_DIR,
    "volumen_bruto": VOLUMEN_BRUTO_DIR,
    "col_bruto":     COL_BRUTO_DIR,
    "tarjetas":      TARJETAS_DIR,
}


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def fetch(start_year: int = FIRST_YEAR) -> dict:
    """Descarga todos los tipos de colocaciones desde start_year hasta hoy."""
    current_year = datetime.today().year
    result = {k: [] for k in _URL_MAP}

    for key in _URL_MAP:
        urls     = _URL_MAP[key]
        dest_dir = _DIR_MAP[key]
        earliest = _EARLIEST[key]

        # ZIP histórico si el start_year cae antes del primer año individual
        if start_year < earliest and "anterior" in urls:
            p = _download_zip(f"{key}_anterior", urls["anterior"], dest_dir,
                              is_historic=True)
            if p:
                result[key].append(p)

        # ZIPs individuales
        for year in range(max(start_year, earliest), current_year + 1):
            url = urls.get(year)
            if not url:
                print(f"[colocaciones] {key} {year}: URL no registrada — "
                      f"actualizar bot_colocaciones.py")
                continue
            p = _download_zip(f"{key}_{year}", url, dest_dir,
                              is_historic=(year < current_year))
            if p:
                result[key].append(p)

    print(f"[colocaciones] "
          f"volumen={len(result['volumen'])}  "
          f"colocaciones={len(result['colocaciones'])}  "
          f"volumen_bruto={len(result['volumen_bruto'])}  "
          f"col_bruto={len(result['col_bruto'])}  "
          f"tarjetas={len(result['tarjetas'])}")
    return result


# ---------------------------------------------------------------------------
# Descarga con detección de cambios via ETag
# ---------------------------------------------------------------------------

def _download_zip(key: str, url: str, dest_dir: Path,
                  is_historic: bool) -> Path | None:
    dest      = dest_dir / f"{key}.zip"
    etag_path = dest_dir / f"{key}.etag"

    if is_historic and dest.exists():
        print(f"[colocaciones] {key}: histórico en disco, omitiendo.")
        return dest

    meta = _get_remote_meta(url)
    if meta is None:
        if dest.exists():
            print(f"[colocaciones] {key}: sin respuesta HEAD; usando local.")
            return dest
        print(f"[colocaciones] {key}: no disponible en SEPS, omitiendo.")
        return None

    remote_etag = meta["etag"] or meta["last_modified"]
    local_etag  = (etag_path.read_text(encoding="utf-8").strip()
                   if etag_path.exists() else "")

    if dest.exists() and remote_etag and local_etag == remote_etag:
        print(f"[colocaciones] {key}: sin cambios (ETag coincide), omitiendo.")
        return dest

    size_mb = f"{meta['size'] / 1e6:.1f} MB" if meta.get("size") else "?"
    print(f"[colocaciones] {key}: descargando ({size_mb})...")
    _stream_download(url, dest)
    if remote_etag:
        etag_path.write_text(remote_etag, encoding="utf-8")
    print(f"[colocaciones] {key}: guardado -> {dest.name}")
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
