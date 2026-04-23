"""
Fuente  : SRI - Recaudación Mensual
URL     : https://www.sri.gob.ec/datasets
Periodicidad: Mensual por año
Instrucción : Apartado Recaudación > "Valores recaudados mensualmente (provincia y
              actividad económica)" > elegir año > descargar > ajustar barra vertical (|).
              Columnas clave: B "MES", I "PROVINCIA", L "VALOR_RECAUDADO".
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader


def extract_fixed_range(start_year: int, end_year: int):
    """Extrae recaudación mensual entre start_year y end_year."""
    df = bot.download(start_year=start_year, end_year=end_year)
    loader.load(df)
    return df


def extract_to_current():
    """Extrae recaudación mensual desde 2018 hasta el año en curso."""
    df = bot.download()
    loader.load(df)
    return df


def extract_to_specific_date(target_year: int):
    """Extrae recaudación mensual hasta target_year."""
    df = bot.download(end_year=target_year)
    loader.load(df)
    return df


if __name__ == "__main__":
    extract_to_current()
