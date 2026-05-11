"""
Fuente      : BCE - Riesgo Pais (EMBI)
URL         : https://contenido.bce.fin.ec/documentos/informacioneconomica/
              SectorExterno/ix_SectorExternoPrin.html#
Periodicidad: Diario (desde 2017-01-01)
Tabla       : riesgo_pais

Modos de ejecucion
------------------
Flujo completo (fetch API + carga BD):
    python main.py

Solo consulta (muestra datos sin cargar BD):
    python main.py --dry-run
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader


def run(dry_run: bool = False) -> None:
    records = bot.fetch()

    if dry_run:
        print(f"[rp] Dry-run: {len(records)} registros obtenidos, sin cargar a BD.")
        if records:
            print(f"  Primero : {records[0]}")
            print(f"  Ultimo  : {records[-1]}")
        return

    loader.load(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ETL — Riesgo Pais EMBI (BCE Ecuador)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Descarga y muestra datos sin insertar en la BD"
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)
