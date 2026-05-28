"""
Fuente      : BCE — Cuentas Nacionales / IMAEc
Dataset     : Índice de Actividad Económica Coyuntural (IMAEc_{YYYYMM}.xlsx)
Periodicidad: Mensual — nuevo archivo cada mes, datos desde 2018.ene
Tablas      :
  imaec_bruto     — hojas _brut_ (2 hojas: actividad + petrolero/no petrolero)
  imaec_ajustado  — hojas _ajus_ (8 hojas: ajustado, vY, contribución,
                    acumulado × 2 grupos)

El bot descubre el archivo vigente desde la página BCE (URL cambia
cada mes) y solo descarga si el ETag cambió.

Modos de ejecución
------------------
    python main.py                  # descarga + ETL
    python main.py --download-only  # solo descarga
    python main.py --etl-only       # ETL sobre archivos ya descargados
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
) -> None:
    if not etl_only:
        files = bot.fetch()
    else:
        files = sorted(DOWNLOAD_DIR.glob("IMAEc_*.xlsx"))
        if not files:
            print("[imaec] Sin archivos IMAEc_ en disco para ETL.")
            return
        print(f"[imaec] ETL sobre {len(files)} archivo(s) en disco.")

    if not download_only and files:
        loader.load(files)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="ETL — IMAEc Índice de Actividad Económica BCE Ecuador"
    )
    ap.add_argument("--download-only", action="store_true",
                    help="Solo descarga el xlsx, sin cargar a BD")
    ap.add_argument("--etl-only", action="store_true",
                    help="Solo ETL sobre archivos ya descargados")
    args = ap.parse_args()

    if args.download_only and args.etl_only:
        ap.error("--download-only y --etl-only son mutuamente excluyentes.")

    run(download_only=args.download_only, etl_only=args.etl_only)
