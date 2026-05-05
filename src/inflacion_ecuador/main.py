"""
Fuente  : INEC - Índice de Precios al Consumidor (IPC)
URL     : https://www.ecuadorencifras.gob.ec/inflacion/
Periodicidad: Mensual (serie histórica desde 1969)
Datos   : SERIE HISTORICA IPC_*.xls — hojas Variación Mensual y Variación Anual

Modos de ejecución
------------------
Flujo completo (descarga + ETL):
    python main.py

Solo descarga (sin ETL):
    python main.py --download-only

Solo ETL desde archivos ya descargados:
    python main.py --etl-only
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader

DOWNLOAD_BASE = Path(__file__).resolve().parents[2] / "downloads" / "inflacion_ecuador"
_SERIE_RE = re.compile(r"SERIE\s*HISTORICA\s*IPC.*\.xls$", re.IGNORECASE)


def _resolve_xls() -> list:
    """Encuentra XLS de serie histórica ya descargados."""
    return [p for p in sorted(DOWNLOAD_BASE.glob("**/*.xls")) if _SERIE_RE.match(p.name)]


def run(download_only: bool = False, etl_only: bool = False) -> None:
    if etl_only:
        paths = _resolve_xls()
        print(f"[inflacion] {len(paths)} XLS encontrados para ETL")
        loader.load(paths)
        return

    result = bot.download_and_extract()
    xls_paths = result["xls_paths"]

    if download_only:
        print(f"Descarga completada — {len(xls_paths)} XLS disponibles")
        return

    loader.load(xls_paths)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ETL — IPC Inflación Ecuador (INEC)"
    )
    parser.add_argument(
        "--download-only", action="store_true",
        help="Solo descarga el ZIP y extrae el XLS, sin cargar a la BD"
    )
    parser.add_argument(
        "--etl-only", action="store_true",
        help="Solo ejecuta el ETL sobre XLS ya descargados (sin bot)"
    )

    args = parser.parse_args()

    if args.download_only and args.etl_only:
        parser.error("--download-only y --etl-only son mutuamente excluyentes.")

    run(download_only=args.download_only, etl_only=args.etl_only)
