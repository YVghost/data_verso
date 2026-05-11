"""
Fuente      : BCE - Información Monetaria Semanal
URL         : https://contenido.bce.fin.ec/documentos/informacioneconomica/
              MonetarioFinanciero/ix_ReportesMonetarios.html
Periodicidad: Semanal (2012 → presente)
Datos       : Hoja IMS5 — depósitos del Gobierno Central en el BCE
              Fila 63: Depósitos transferibles GC
              Fila 74: Gobierno Central
              Filas 79-80: Otros depósitos GC

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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader

DOWNLOAD_BASE = Path(__file__).resolve().parents[2] / "downloads" / "depositos_gobierno_bce"


def _resolve_files() -> list:
    """Encuentra todos los .xls/.xlsx ya descargados."""
    files = sorted(DOWNLOAD_BASE.glob("**/*.xls*"))
    return [f for f in files if not f.name.startswith("~")]


def run(download_only: bool = False, etl_only: bool = False) -> None:
    if etl_only:
        paths = _resolve_files()
        print(f"[bce] {len(paths)} archivos encontrados para ETL")
        loader.load(paths)
        return

    result = bot.download_and_extract()
    paths = result["files"]

    if download_only:
        print(f"Descarga completada — {len(paths)} archivos disponibles")
        return

    loader.load(paths)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ETL — Depósitos Gobierno Central en BCE (Semanal)"
    )
    parser.add_argument(
        "--download-only", action="store_true",
        help="Solo descarga los XLS, sin cargar a la BD"
    )
    parser.add_argument(
        "--etl-only", action="store_true",
        help="Solo ejecuta el ETL sobre archivos ya descargados (sin bot)"
    )

    args = parser.parse_args()

    if args.download_only and args.etl_only:
        parser.error("--download-only y --etl-only son mutuamente excluyentes.")

    run(download_only=args.download_only, etl_only=args.etl_only)
