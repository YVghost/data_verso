"""
Fuente      : BCE - Reservas Internacionales
URL         : https://contenido.bce.fin.ec/documentos/informacioneconomica/
              MonetarioFinanciero/ix_ReservasInternacionales.html
Periodicidad: Mensual (2000 -> presente)
Tablas      : reservas_internacionales_anual
              reservas_internacionales_mensual

Modos de ejecucion
------------------
Flujo completo (descarga + ETL):
    python main.py

Solo descarga (sin ETL):
    python main.py --download-only

Solo ETL desde archivo ya descargado:
    python main.py --etl-only
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader

DOWNLOAD_FILE = Path(__file__).resolve().parents[2] / "downloads" / "reservas_internacionales" / "ReservasInternacionales.xlsx"


def run(download_only: bool = False, etl_only: bool = False) -> None:
    if etl_only:
        if not DOWNLOAD_FILE.exists():
            print(f"[ri] Archivo no encontrado: {DOWNLOAD_FILE}")
            return
        loader.load(DOWNLOAD_FILE)
        return

    result = bot.download_and_extract()
    file   = result.get("file")

    if download_only:
        if file:
            print(f"Descarga completada: {file.name} ({file.stat().st_size:,} bytes)")
        return

    if file:
        loader.load(file)
    else:
        print("[ri] No hay archivo disponible para cargar.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ETL — Reservas Internacionales BCE"
    )
    parser.add_argument(
        "--download-only", action="store_true",
        help="Solo descarga el Excel, sin cargar a la BD"
    )
    parser.add_argument(
        "--etl-only", action="store_true",
        help="Solo ejecuta el ETL sobre el archivo ya descargado (sin bot)"
    )

    args = parser.parse_args()

    if args.download_only and args.etl_only:
        parser.error("--download-only y --etl-only son mutuamente excluyentes.")

    run(download_only=args.download_only, etl_only=args.etl_only)
