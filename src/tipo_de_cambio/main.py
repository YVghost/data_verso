"""
Fuente      : BCE - Indice de Tipo de Cambio Real (ITCER)
URL         : https://contenido.bce.fin.ec/documentos/informacioneconomica/
              SectorExterno/ix_TipoCambioReal.html
Periodicidad: Mensual (desde 1995) y Anual
Tablas      : tipo_de_cambio_anual
              tipo_de_cambio_mensual

El bot detecta automaticamente el anio base mas reciente (2018=100, 2025=100, etc.)
para ser robusto ante futuros cambios de nombre del archivo.

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

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "tipo_de_cambio"


def _find_local_file() -> Path | None:
    """Busca cualquier Excel ITCER ya descargado."""
    files = sorted(DOWNLOAD_DIR.glob("IndicesTipoCambioReal-*_100.xlsx"))
    return files[-1] if files else None


def run(download_only: bool = False, etl_only: bool = False) -> None:
    if etl_only:
        f = _find_local_file()
        if not f:
            print("[tc] No se encontro archivo local. Ejecuta sin --etl-only primero.")
            return
        loader.load(f)
        return

    result = bot.download_and_extract()
    f = result.get("file")

    if download_only:
        if f:
            print(f"Descarga completada: {f.name} ({f.stat().st_size:,} bytes)")
        return

    if f:
        loader.load(f)
    else:
        print("[tc] No hay archivo disponible para cargar.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ETL - Indice Tipo de Cambio Real BCE Ecuador"
    )
    parser.add_argument("--download-only", action="store_true",
                        help="Solo descarga el Excel, sin cargar a BD")
    parser.add_argument("--etl-only", action="store_true",
                        help="Solo ETL sobre archivo ya descargado")
    args = parser.parse_args()

    if args.download_only and args.etl_only:
        parser.error("--download-only y --etl-only son mutuamente excluyentes.")

    run(download_only=args.download_only, etl_only=args.etl_only)
