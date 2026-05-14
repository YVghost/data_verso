"""
Fuente      : SRI - Recaudacion Mensual
URL         : https://descargas.sri.gob.ec/download/datosAbiertos/sri_recaudacion_{YEAR}.csv
Periodicidad: Anual (2017-presente), con datos mensuales dentro de cada archivo
Tabla       : recaudacion_mensual

Modos de ejecucion
------------------
    python main.py                  # descarga + ETL (2017 al anio actual)
    python main.py --download-only  # solo descarga
    python main.py --etl-only       # ETL sobre archivos ya en disco
    python main.py --start 2022     # desde 2022 al anio actual
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "recaudacion_mensual"


def run(
    download_only: bool = False,
    etl_only: bool = False,
    start_year: int = bot.FIRST_YEAR,
) -> None:
    if not etl_only:
        files = bot.fetch(start_year=start_year)
    else:
        files = sorted(DOWNLOAD_DIR.glob("sri_recaudacion_*.csv"))
        if not files:
            print("[recaudacion] Sin archivos en disco para ETL.")
            return

    if download_only:
        return

    loader.load(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ETL - Recaudacion Mensual SRI Ecuador"
    )
    parser.add_argument(
        "--download-only", action="store_true",
        help="Solo descarga archivos CSV, sin cargar a la BD"
    )
    parser.add_argument(
        "--etl-only", action="store_true",
        help="Solo ETL sobre archivos ya descargados"
    )
    parser.add_argument(
        "--start", type=int, default=bot.FIRST_YEAR, metavar="YEAR",
        help=f"Anio de inicio (default: {bot.FIRST_YEAR})"
    )
    args = parser.parse_args()

    if args.download_only and args.etl_only:
        parser.error("--download-only y --etl-only son mutuamente excluyentes.")

    run(
        download_only=args.download_only,
        etl_only=args.etl_only,
        start_year=args.start,
    )