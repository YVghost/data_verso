"""
Fuente      : BCE - PIB Per Capita Nominal
URL         : https://contenido.bce.fin.ec/documentos/informacioneconomica/
              indicadores/real/PIBPerCapita.html
JSON        : datos_cna.json (mismo archivo que otros indicadores CNA)
Periodicidad: Anual (2000-presente)
Tabla       : pib_per_capita_nominal

No requiere Playwright — JSON directo del BCE.

Modos de ejecucion
------------------
    python main.py              # fetch + carga BD
    python main.py --dry-run    # muestra datos sin cargar
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
        print(f"[pib_pc] Dry-run: {len(records)} registros, sin cargar a BD.")
        for r in records:
            print(f"  {r['anio']}  USD {r['pib_per_capita_usd']:,.1f}")
        return

    loader.load(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ETL - PIB Per Capita Nominal BCE Ecuador"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Muestra los datos sin insertar en la BD")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
