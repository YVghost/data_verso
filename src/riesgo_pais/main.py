"""
Fuente  : BCE - Riesgo País (EMBI)
URL     : https://contenido.bce.fin.ec/documentos/informacioneconomica/SectorExterno/ix_SectorExternoPrin.html#
Periodicidad: Diario/semanal (histórico desde 2004)
Instrucción : Parte inferior > Riesgo País > tres puntos izquierdos > Serie Histórica >
              nueva pestaña > tres líneas superiores izquierdas > Descargar Excel "riesgo-pas".
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader


def extract_fixed_range(start_date: str, end_date: str):
    """Extrae riesgo país entre start_date y end_date (YYYY-MM-DD)."""
    df = bot.download(start=start_date, end=end_date)
    loader.load(df)
    return df


def extract_to_current():
    """Extrae riesgo país desde 2004 hasta hoy."""
    df = bot.download()
    loader.load(df)
    return df


def extract_to_specific_date(target_date: str):
    """Extrae riesgo país hasta una fecha específica (YYYY-MM-DD)."""
    df = bot.download(end=target_date)
    loader.load(df)
    return df


if __name__ == "__main__":
    extract_to_current()
