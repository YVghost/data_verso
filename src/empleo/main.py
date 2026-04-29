"""
Fuente  : INEC - ENEMDU Trimestral y Mensual (Mercado Laboral)
URLs    :
  Trimestral: https://www.ecuadorencifras.gob.ec/enemdu-trimestral/
  Mensual:    https://www.ecuadorencifras.gob.ec/estadisticas-laborales-enemdu/
Periodicidad: Trimestral (desde 2020) | Mensual (histórico desde 2007)
Datos   : Tabulados de Mercado Laboral en CSV (ZIPs con datos históricos completos)

Nota: cada ZIP ya contiene todos los períodos históricos disponibles.
      El filtro --start / --end se aplica en el loader (ETL), no en la descarga.

Modos de ejecución
------------------
Flujo completo (trimestral + mensual):
    python main.py
    python main.py --start 2022 --end 2024

Solo un tipo de período:
    python main.py --tipo trimestral
    python main.py --tipo mensual

Solo descarga (sin ETL):
    python main.py --download-only
    python main.py --download-only --tipo mensual

Solo ETL desde archivos ya descargados:
    python main.py --etl-only
    python main.py --etl-only --tipo trimestral --start 2022
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader

DOWNLOAD_BASE = Path(__file__).resolve().parents[2] / "downloads" / "empleo"

_TRIMESTRAL_QUARTERS = {"I", "II", "III", "IV"}


def _is_trimestral_folder(name: str) -> bool:
    return name.upper() in _TRIMESTRAL_QUARTERS


def _is_mensual_folder(name: str) -> bool:
    return len(name) == 6 and name.isdigit()


def _resolve_csvs(tipo: str = "all") -> list:
    """
    Encuentra CSVs ya descargados filtrando por tipo de período.
    Estructura: downloads/empleo/{año}/{periodo}/archivo.csv
      periodo = I/II/III/IV → trimestral
      periodo = YYYYMM      → mensual
    """
    paths = []
    for p in sorted(DOWNLOAD_BASE.glob("*/*/*.csv")):
        if bot._should_skip(p.name):
            continue
        folder = p.parent.name
        if tipo == "trimestral" and not _is_trimestral_folder(folder):
            continue
        if tipo == "mensual" and not _is_mensual_folder(folder):
            continue
        paths.append(p)
    return paths


def run(
    start_year: int = None,
    end_year: int = None,
    download_only: bool = False,
    etl_only: bool = False,
    tipo: str = "all",
) -> None:
    """
    Punto de entrada unificado.
    tipo: "all" | "trimestral" | "mensual"
    """
    if etl_only:
        paths = _resolve_csvs(tipo)
        print(f"[empleo] {len(paths)} CSVs encontrados para ETL (tipo={tipo})")
        loader.load(paths, start_year=start_year, end_year=end_year)
        return

    all_csvs = []

    if tipo in ("all", "trimestral"):
        result = bot.download_and_extract()
        all_csvs.extend(result["csvs"])

    if tipo in ("all", "mensual"):
        result = bot.download_and_extract_monthly()
        all_csvs.extend(result["csvs"])

    if download_only:
        print(f"Descarga completada — {len(all_csvs)} CSVs disponibles")
        return

    loader.load(all_csvs, start_year=start_year, end_year=end_year)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ETL — ENEMDU Mercado Laboral Trimestral y Mensual (INEC)"
    )
    parser.add_argument(
        "--start", type=int, default=None,
        help="Año inicial para filtrar períodos en el ETL (por defecto: todos)"
    )
    parser.add_argument(
        "--end", type=int, default=None,
        help="Año final para filtrar períodos en el ETL (por defecto: todos)"
    )
    parser.add_argument(
        "--download-only", action="store_true",
        help="Solo descarga los ZIPs y extrae CSVs, sin cargar a la BD"
    )
    parser.add_argument(
        "--etl-only", action="store_true",
        help="Solo ejecuta el ETL sobre CSVs ya descargados (sin bot)"
    )
    parser.add_argument(
        "--tipo", choices=["all", "trimestral", "mensual"], default="all",
        help="Tipo de período a procesar: all | trimestral | mensual (por defecto: all)"
    )

    args = parser.parse_args()

    if args.download_only and args.etl_only:
        parser.error("--download-only y --etl-only son mutuamente excluyentes.")

    run(
        start_year=args.start,
        end_year=args.end,
        download_only=args.download_only,
        etl_only=args.etl_only,
        tipo=args.tipo,
    )
