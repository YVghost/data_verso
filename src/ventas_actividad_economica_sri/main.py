"""
Fuente      : SRI Ecuador — Ventas / Ingresos por Actividad Economica CIIU
Sistema     : Saiku REST API (srienlinea.sri.gob.ec/saiku/) — sin autenticacion
Extraccion  : Automatica via API REST
Periodicidad: Anual (2018-presente)
Tablas      :
  ventas_ingresos_101       — Total Ingresos (699) Form 101
  ventas_vnl12_101          — Ventas Netas Locales 12% (601) Form 101
  ventas_vnl0_101           — Ventas Netas Locales 0% (602) Form 101
  ventas_exportaciones_104  — Total Ventas y Exportaciones (419) Form 104
  ventas_dependencia_103    — Retenciones Relacion de Dependencia (270) Form 103
  ventas_honorarios_103     — Honorarios Profesionales (320) Form 103

Modos de ejecucion
------------------
    python main.py                  # consulta API + carga BD
    python main.py --download-only  # solo consulta API, sin cargar BD
    python main.py --etl-only       # igual que la ejecucion normal
    python main.py --start 2020     # desde 2020
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader


def run(
    download_only: bool = False,
    etl_only:      bool = False,
    start_year:    int  = bot.FIRST_YEAR,
) -> None:
    data = bot.fetch(start_year=start_year)

    if not download_only:
        loader.load(data)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="ETL - Ventas por Actividad Economica SRI (CIIU) via Saiku API"
    )
    ap.add_argument("--download-only", action="store_true",
                    help="Solo consulta API, sin cargar a la BD")
    ap.add_argument("--etl-only", action="store_true",
                    help="Igual que ejecucion normal (siempre consulta API)")
    ap.add_argument("--start", type=int, default=bot.FIRST_YEAR, metavar="YEAR",
                    help=f"Anio de inicio (default: {bot.FIRST_YEAR})")
    args = ap.parse_args()

    if args.download_only and args.etl_only:
        ap.error("--download-only y --etl-only son mutuamente excluyentes.")

    run(
        download_only=args.download_only,
        etl_only=args.etl_only,
        start_year=args.start,
    )
