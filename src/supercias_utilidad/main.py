"""
Fuente      : Superintendencia de Compañías, Valores y Seguros (Supercias)
Dataset     : Ranking de empresas Ecuador — ranking_{YYYY}.xlsx
Periodicidad: Anual (publicación aprox. mayo-junio de cada año)
Tabla       : supercias_utilidad

Cobertura   : 2010 - año actual
              El archivo del año anterior siempre se re-verifica (ETag)
              ya que Supercias puede actualizarlo tras la publicación inicial.
              El archivo del año en curso se intenta descargar; si no está
              disponible aún (404) se omite sin error.

Modos de ejecución
------------------
    python main.py                  # descarga + ETL completo (2010-presente)
    python main.py --download-only  # solo descarga xlsx
    python main.py --etl-only       # ETL sobre archivos ya descargados
    python main.py --start 2020     # desde 2020
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
        files = sorted(DOWNLOAD_DIR.glob("ranking_*.xlsx"))
        if not files:
            print("[supercias] Sin archivos ranking_ en disco para ETL.")
            return
        if start_year > bot.FIRST_YEAR:
            files = [f for f in files
                     if int(f.stem.split("_")[-1]) >= start_year]
        print(f"[supercias] ETL sobre {len(files)} archivo(s) en disco.")

    if not download_only and files:
        loader.load(files)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="ETL — Ranking Empresas Supercias Ecuador"
    )
    ap.add_argument("--download-only", action="store_true",
                    help="Solo descarga los xlsx, sin cargar a BD")
    ap.add_argument("--etl-only", action="store_true",
                    help="Solo ETL sobre archivos ya descargados")
    ap.add_argument("--start", type=int, default=bot.FIRST_YEAR, metavar="YEAR",
                    help=f"Año de inicio (default: {bot.FIRST_YEAR})")
    args = ap.parse_args()

    if args.download_only and args.etl_only:
        ap.error("--download-only y --etl-only son mutuamente excluyentes.")

    run(
        download_only=args.download_only,
        etl_only=args.etl_only,
        start_year=args.start,
    )
