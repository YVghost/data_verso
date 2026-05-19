"""
Fuente      : SEPS - Mutualistas Ecuador
URL         : https://estadisticas.seps.gob.ec/index.php/estadisticas-sfps/
Periodicidad: Mensual (archivos anuales)
Tablas      :
  Captaciones  : mutualistas_captaciones, mutualistas_captaciones_sectores,
                 mutualistas_captaciones_bruto
  Colocaciones : mutualistas_colocaciones_volumen_credito,
                 mutualistas_colocaciones_volumen_credito_sectores,
                 mutualistas_colocaciones, mutualistas_colocaciones_sectores,
                 mutualistas_colocaciones_volumen_credito_bruto,
                 mutualistas_colocaciones_mensual_bruto,
                 mutualistas_colocaciones_tarjetas_con_forma_pago,
                 mutualistas_colocaciones_tarjetas_sin_forma_pago

Modos de ejecucion
------------------
    python main.py                  # descarga + ETL completo (2017 al año actual)
    python main.py --download-only  # solo descarga ZIPs
    python main.py --etl-only       # ETL sobre ZIPs ya en disco
    python main.py --start 2022     # desde 2022
    python main.py --captaciones    # solo captaciones
    python main.py --colocaciones   # solo colocaciones
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import bot_colocaciones as bot_col
import loader_captaciones as loader_cap
import loader_colocaciones as loader_col

REPORTES_DIR = bot.REPORTES_DIR
BASES_DIR    = bot.BASES_DIR


def run(
    download_only: bool = False,
    etl_only: bool = False,
    start_year: int = bot.FIRST_YEAR,
    only_captaciones: bool = False,
    only_colocaciones: bool = False,
) -> None:
    run_cap = not only_colocaciones
    run_col = not only_captaciones

    # ------------------------------------------------------------------ #
    # Captaciones                                                          #
    # ------------------------------------------------------------------ #
    if run_cap:
        if not etl_only:
            files_cap = bot.fetch(start_year=start_year)
        else:
            reportes = sorted(REPORTES_DIR.glob("*.zip"))
            bases    = sorted(BASES_DIR.glob("*.zip"))
            files_cap = {"reportes": reportes, "bases": bases}
            if not reportes and not bases:
                print("[mutualistas] Sin ZIPs de captaciones en disco para ETL.")
                files_cap = None

        if not download_only and files_cap:
            files_cap["min_year"] = start_year
            loader_cap.load(files_cap)

    # ------------------------------------------------------------------ #
    # Colocaciones                                                         #
    # ------------------------------------------------------------------ #
    if run_col:
        if not etl_only:
            files_col = bot_col.fetch(start_year=start_year)
        else:
            col_dirs = {
                "volumen":       bot_col.VOLUMEN_DIR,
                "colocaciones":  bot_col.COLOCACIONES_DIR,
                "volumen_bruto": bot_col.VOLUMEN_BRUTO_DIR,
                "col_bruto":     bot_col.COL_BRUTO_DIR,
                "tarjetas":      bot_col.TARJETAS_DIR,
            }
            files_col = {k: sorted(d.glob("*.zip"))
                         for k, d in col_dirs.items()}
            if not any(files_col.values()):
                print("[mutualistas] Sin ZIPs de colocaciones en disco para ETL.")
                files_col = None

        if not download_only and files_col:
            files_col["min_year"] = start_year
            loader_col.load(files_col)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="ETL - Mutualistas SEPS Ecuador (captaciones + colocaciones)"
    )
    ap.add_argument("--download-only", action="store_true",
                    help="Solo descarga ZIPs, sin cargar a la BD")
    ap.add_argument("--etl-only", action="store_true",
                    help="Solo ETL sobre ZIPs ya descargados")
    ap.add_argument("--start", type=int, default=bot.FIRST_YEAR, metavar="YEAR",
                    help=f"Año de inicio (default: {bot.FIRST_YEAR})")
    ap.add_argument("--captaciones", action="store_true",
                    help="Ejecutar solo el flujo de captaciones")
    ap.add_argument("--colocaciones", action="store_true",
                    help="Ejecutar solo el flujo de colocaciones")
    args = ap.parse_args()

    if args.download_only and args.etl_only:
        ap.error("--download-only y --etl-only son mutuamente excluyentes.")
    if args.captaciones and args.colocaciones:
        ap.error("--captaciones y --colocaciones son mutuamente excluyentes.")

    run(
        download_only=args.download_only,
        etl_only=args.etl_only,
        start_year=args.start,
        only_captaciones=args.captaciones,
        only_colocaciones=args.colocaciones,
    )
