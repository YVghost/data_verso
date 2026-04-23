"""
Fuente  : BCE - PIB Nominal Trimestral
URL     : https://contenido.bce.fin.ec/documentos/Administracion/bi_menuCNTdef.html?utm
Periodicidad: Trimestral
Instrucción : Pestaña Descargas > Datos > Exportar. Excel "PUB - PIB Trimestral",
              hoja "SeriesCT1", columnas: Año, Trimestre, PIB Constante.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader


def extract_fixed_range(start_year: int, end_year: int):
    """Extrae PIB Nominal trimestral entre start_year y end_year."""
    df = bot.download(start_year=start_year, end_year=end_year)
    loader.load(df)
    return df


def extract_to_current():
    """Extrae PIB Nominal trimestral desde el inicio del histórico hasta hoy."""
    df = bot.download()
    loader.load(df)
    return df


def extract_to_specific_date(target_year: int):
    """Extrae PIB Nominal trimestral hasta target_year."""
    df = bot.download(end_year=target_year)
    loader.load(df)
    return df


if __name__ == "__main__":
    extract_to_current()
