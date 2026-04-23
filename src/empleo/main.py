"""
Fuente  : INEC - ENEMDU Trimestral (Mercado Laboral)
URL     : https://www.ecuadorencifras.gob.ec/enemdu-trimestral/
Periodicidad: Trimestral
Instrucción : Panel azul izquierdo > ENEMDU Trimestral > descargar
              "202602_Tabulados_Mercado_Laboral_EXCEL", hoja "1. Poblaciones".
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader


def extract_fixed_range(start_date: str, end_date: str):
    """Extrae datos de empleo entre start_date y end_date (YYYY-MM-DD)."""
    df = bot.download(start=start_date, end=end_date)
    loader.load(df)
    return df


def extract_to_current():
    """Extrae datos de empleo desde el inicio del histórico hasta hoy."""
    df = bot.download()
    loader.load(df)
    return df


def extract_to_specific_date(target_date: str):
    """Extrae datos de empleo hasta una fecha específica (YYYY-MM-DD)."""
    df = bot.download(end=target_date)
    loader.load(df)
    return df


if __name__ == "__main__":
    extract_to_current()
