"""
Fuente      : BCE - Cuentas Nacionales Trimestrales
Pagina      : https://contenido.bce.fin.ec/documentos/informacioneconomica/
              cuentasnacionales/ix_cuentasnacionalestrimestrales.html
Archivos    : vab_{cod}_{YYYYQQ}.xlsx  (Valor Agregado Bruto por Industrias)
Periodicidad: Trimestral (archivos anuales actualizados)
Tablas      : pib_nominal_industria_bruto  (hojas Datos Brutos)
              pib_nominal_industria        (hojas Datos Ajustados)

Modos de ejecucion
------------------
    python main.py                    # descarga + ETL completo
    python main.py --download-only    # solo descarga Excel
    python main.py --etl-only         # ETL sobre Excel ya en disco
    python main.py --start 2024       # desde 2024
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
    etl_only:      bool = False,
    start_year:    int  = bot.FIRST_YEAR,
) -> None:
    if not etl_only:
        files = bot.fetch(start_year=start_year)
    else:
        files = sorted(DOWNLOAD_DIR.glob("vab_*.xlsx"))
        if not files:
            print("[vab_industria] Sin archivos Excel en disco para ETL.")
            return
        print(f"[vab_industria] ETL-only: {len(files)} archivos en disco.")

    if not download_only and files:
        loader.load(files)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="ETL - PIB Nominal Industria BCE (VAB Trimestrales)"
    )
    ap.add_argument("--download-only", action="store_true",
                    help="Solo descarga Excel, sin cargar a la BD")
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
