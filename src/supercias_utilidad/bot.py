"""
Bot de descarga: Ranking de Empresas Supercias — Ecuador

Fuente: Superintendencia de Compañías, Valores y Seguros
URL   : https://appscvsmovil.supercias.gob.ec/ranking/recursos/archivos/ranking_{YYYY}.xlsx

Cobertura: 2010 - año actual (archivo anual, publicado aprox. mayo-junio)
El archivo del año anterior siempre se re-verifica con ETag porque
Supercias puede actualizarlo después de la publicación inicial.

El servidor usa TLS legacy (SSLv3); se usa un adaptador con ciphers
permisivos y verificación desactivada solo para este host.
"""

import ssl
import warnings
from datetime import datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "supercias_utilidad"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

FIRST_YEAR = 2010
TIMEOUT    = 120
_BASE_URL  = "https://appscvsmovil.supercias.gob.ec/ranking/recursos/archivos"
_HEADERS   = {"User-Agent": "Mozilla/5.0"}


# ---------------------------------------------------------------------------
# SSL legacy adapter (Supercias usa TLS anticuado)
# ---------------------------------------------------------------------------

class _LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **kw):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        kw["ssl_context"] = ctx
        return super().proxy_manager_for(proxy, **kw)


def _make_session() -> requests.Session:
    s = requests.Session()
    s.mount("https://", _LegacySSLAdapter())
    return s


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def fetch(start_year: int = FIRST_YEAR) -> list[Path]:
    """
    Descarga ranking_{YYYY}.xlsx desde start_year hasta el año actual.
    - Archivos históricos (< año_actual - 1): omite si ya están en disco.
    - Año anterior y año actual: siempre re-verifica con ETag.
    - Si el archivo del año actual no existe aún (404): lo omite sin error.

    Retorna lista de rutas disponibles en disco.
    """
    current_year = datetime.today().year
    session = _make_session()
    files: list[Path] = []

    for year in range(start_year, current_year + 1):
        fname = f"ranking_{year}.xlsx"
        url   = f"{_BASE_URL}/{fname}"
        is_recent = (year >= current_year - 1)

        path = _download_file(fname, url, session, is_recent)
        if path:
            files.append(path)

    print(f"[supercias] {len(files)} archivo(s) disponibles en disco.")
    return files


# ---------------------------------------------------------------------------
# Descarga con ETag
# ---------------------------------------------------------------------------

def _download_file(
    fname: str, url: str,
    session: requests.Session,
    is_recent: bool,
) -> Path | None:
    dest      = DOWNLOAD_DIR / fname
    etag_path = DOWNLOAD_DIR / (fname + ".etag")

    # Histórico ya en disco: no re-descargar
    if dest.exists() and not is_recent:
        print(f"[supercias] {fname}: histórico en disco, omitiendo.")
        return dest

    meta = _get_remote_meta(url, session)
    if meta is None:
        if dest.exists():
            print(f"[supercias] {fname}: sin respuesta remota; usando local.")
            return dest
        # Archivo del año actual aún no publicado
        print(f"[supercias] {fname}: no disponible aún, omitiendo.")
        return None

    remote_etag = meta["etag"] or meta["last_modified"]
    local_etag  = etag_path.read_text(encoding="utf-8").strip() if etag_path.exists() else ""

    if dest.exists() and remote_etag and local_etag == remote_etag:
        print(f"[supercias] {fname}: sin cambios (ETag coincide), omitiendo.")
        return dest

    size_mb = f"{meta['size'] / 1e6:.1f} MB" if meta.get("size") else "?"
    print(f"[supercias] Descargando {fname} ({size_mb})...")
    _stream_download(url, dest, session)
    if remote_etag:
        etag_path.write_text(remote_etag, encoding="utf-8")
    print(f"[supercias] {fname}: guardado.")
    return dest


def _get_remote_meta(url: str, session: requests.Session) -> dict | None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            resp = session.head(url, timeout=30, headers=_HEADERS, verify=False)
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


def _stream_download(url: str, dest: Path, session: requests.Session) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with session.get(url, timeout=TIMEOUT, stream=True,
                         headers=_HEADERS, verify=False) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
