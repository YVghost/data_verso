"""
Fuente  : BCE - Cuentas Nacionales Trimestrales (PIB desagregado por industria)
URL     : https://contenido.bce.fin.ec/documentos/informacioneconomica/cuentasnacionales/ix_cuentasnacionalestrimestrales.html
Periodicidad: Trimestral
Instrucción : Descargar Excel desde la sección de Cuentas Nacionales Trimestrales,
              extraer columnas de Año, Trimestre, Industria y valor en USD constantes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader


def extract_fixed_range(start_year: int, end_year: int):
    """Extrae PIB por industria trimestral entre start_year y end_year."""
    df = bot.download(start_year=start_year, end_year=end_year)
    loader.load(df)
    return df


def extract_to_current():
    """Extrae PIB por industria trimestral desde el inicio del histórico hasta hoy."""
    df = bot.download()
    loader.load(df)
    return df


def extract_to_specific_date(target_year: int):
    """Extrae PIB por industria trimestral hasta target_year."""
    df = bot.download(end_year=target_year)
    loader.load(df)
    return df


if __name__ == "__main__":
    extract_to_current()
