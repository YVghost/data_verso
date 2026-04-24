"""
Fuente  : Superbancos - Captaciones (DEPÓSITOS) y Colocaciones (CARTERA) Instituciones Públicas
URL     : https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-instituciones-publicas/
Periodicidad: Mensual por año

Modos de ejecución
------------------
Flujo completo (descarga + ETL):
    python main.py
    python main.py --start 2020 --end 2024
    python main.py --end 2023

Solo descarga (sin carga a BD):
    python main.py --download-only
    python main.py --download-only --start 2022

Solo ETL desde archivos ya descargados:
    python main.py --etl-only
    python main.py --etl-only --mode depositos
    python main.py --etl-only --mode cartera

Flujo completo de un tipo específico:
    python main.py --mode depositos
    python main.py --mode cartera --start 2021
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader_depositos
import loader_cartera

DOWNLOAD_BASE = Path(__file__).resolve().parents[2] / "downloads" / "captaciones_financiero_publico"


def _resolve_paths(mode: str) -> list:
    paths = sorted(DOWNLOAD_BASE.glob(f"*/{mode}/*.xlsx"))
    return [p for p in paths if not p.name.startswith("~$")]


def run(
    start_year: int = None,
    end_year: int = None,
    download_only: bool = False,
    etl_only: bool = False,
    mode: str = "all",
) -> None:
    """
    Punto de entrada unificado.
    mode: "all" | "depositos" | "cartera"
    """
    if etl_only:
        if mode in ("all", "depositos"):
            paths = _resolve_paths("depositos")
            print(f"[depositos_pub] {len(paths)} archivos encontrados")
            loader_depositos.load(paths)
        if mode in ("all", "cartera"):
            paths = _resolve_paths("cartera")
            print(f"[cartera_pub] {len(paths)} archivos encontrados")
            loader_cartera.load(paths)
        return

    paths = bot.download_and_extract(start_year=start_year, end_year=end_year)

    if download_only:
        dep  = len(paths.get("depositos", []))
        cart = len(paths.get("cartera", []))
        print(f"Descarga completada — depósitos: {dep} archivos, cartera: {cart} archivos")
        return

    if mode in ("all", "depositos"):
        loader_depositos.load(paths["depositos"])
    if mode in ("all", "cartera"):
        loader_cartera.load(paths["cartera"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ETL — Captaciones y Cartera Instituciones Financieras Públicas (Superbancos)"
    )
    parser.add_argument(
        "--start", type=int, default=None,
        help="Año inicial de descarga (por defecto: 2016)"
    )
    parser.add_argument(
        "--end", type=int, default=None,
        help="Año final de descarga (por defecto: año actual)"
    )
    parser.add_argument(
        "--download-only", action="store_true",
        help="Solo descarga ZIPs y extrae Excels, sin cargar a la BD"
    )
    parser.add_argument(
        "--etl-only", action="store_true",
        help="Solo ejecuta el ETL sobre archivos ya descargados (sin bot)"
    )
    parser.add_argument(
        "--mode", choices=["all", "depositos", "cartera"], default="all",
        help="Tipo de dato a procesar (por defecto: all)"
    )

    args = parser.parse_args()

    if args.download_only and args.etl_only:
        parser.error("--download-only y --etl-only son mutuamente excluyentes.")

    run(
        start_year=args.start,
        end_year=args.end,
        download_only=args.download_only,
        etl_only=args.etl_only,
        mode=args.mode,
    )
