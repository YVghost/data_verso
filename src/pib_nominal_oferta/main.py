"""
Fuente      : BCE — Cuentas Nacionales Trimestrales
Dataset     : Oferta y Utilización de Bienes y Servicios (tou_*.xlsx)
Periodicidad: Trimestral (ediciones por trimestre 2023-presente)
Tablas      :
  pib_nominal_oferta_bruto     — hojas _bru (3 tipos de índice)
  pib_nominal_oferta_ajustado  — hojas _ajus (9 tipos de índice)

Modos de ejecución
------------------
    python main.py                  # descarga + ETL completo
    python main.py --download-only  # solo descarga xlsx
    python main.py --etl-only       # ETL sobre archivos ya descargados
    python main.py --start 2024     # ediciones desde 2024
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader

DOWNLOAD_DIR = bot.DOWNLOAD_DIR


def run(
    download_only: bool = False,
    etl_only: bool = False,
    start_year: int = bot.FIRST_YEAR,
) -> None:
    if not etl_only:
        files = bot.fetch(start_year=start_year)
    else:
        files = sorted(DOWNLOAD_DIR.glob("tou_*.xlsx"))
        if not files:
            print("[pib_oferta] Sin archivos tou_ en disco para ETL.")
            return
        print(f"[pib_oferta] ETL sobre {len(files)} archivo(s) en disco.")

    if not download_only and files:
        loader.load(files)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="ETL — PIB Nominal Oferta y Utilización BCE Ecuador"
    )
    ap.add_argument("--download-only", action="store_true",
                    help="Solo descarga los xlsx, sin cargar a BD")
    ap.add_argument("--etl-only", action="store_true",
                    help="Solo ETL sobre archivos ya descargados")
    ap.add_argument("--start", type=int, default=bot.FIRST_YEAR, metavar="YEAR",
                    help=f"Año de edición inicial (default: {bot.FIRST_YEAR})")
    args = ap.parse_args()

    if args.download_only and args.etl_only:
        ap.error("--download-only y --etl-only son mutuamente excluyentes.")

    run(
        download_only=args.download_only,
        etl_only=args.etl_only,
        start_year=args.start,
    )
