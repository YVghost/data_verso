"""
Fuente  : Superbancos - Captaciones Sistema Financiero Público (Depósitos)
URL     : https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-instituciones-publicas/
Periodicidad: Mensual por año (ZIP por año > Excel "BANCA PUBLICA - CAPTACIONES ENE - DIC YYYY.xlsx")
Instrucción : Por cada año disponible (2016-actual) descargar el ZIP de captaciones,
              extraer el Excel y leer los totales de depósitos por provincia.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader


def extract_fixed_range(start_year: int, end_year: int):
    """Extrae captaciones públicas entre start_year y end_year."""
    df = bot.download(start_year=start_year, end_year=end_year)
    loader.load(df)
    return df


def extract_to_current():
    """Extrae captaciones públicas desde 2016 hasta el año en curso."""
    df = bot.download()
    loader.load(df)
    return df


def extract_to_specific_date(target_year: int):
    """Extrae captaciones públicas desde 2016 hasta target_year."""
    df = bot.download(end_year=target_year)
    loader.load(df)
    return df


if __name__ == "__main__":
    extract_to_current()
