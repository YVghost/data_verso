"""
Fuente  : BCE - PIB per cápita nominal
URL     : https://contenido.bce.fin.ec/documentos/informacioneconomica/SectorReal/ix_SectorRealPrin.html#
Periodicidad: Anual
Instrucción : Sector Real > PIB per cápita nominal > tres puntos > Serie Histórica >
              rango 2000-2025 > tres rayas > Descargar Excel ("pib-per-cpita-nominal").
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader


def extract_fixed_range(start_year: int, end_year: int):
    """Extrae PIB per cápita nominal entre start_year y end_year."""
    df = bot.download(start_year=start_year, end_year=end_year)
    loader.load(df)
    return df


def extract_to_current():
    """Extrae PIB per cápita nominal desde 2000 hasta el año en curso."""
    df = bot.download()
    loader.load(df)
    return df


def extract_to_specific_date(target_year: int):
    """Extrae PIB per cápita nominal hasta target_year."""
    df = bot.download(end_year=target_year)
    loader.load(df)
    return df


if __name__ == "__main__":
    extract_to_current()
