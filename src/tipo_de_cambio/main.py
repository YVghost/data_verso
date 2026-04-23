"""
Fuente  : BCE - Índice de Tipo de Cambio Real
URL     : https://contenido.bce.fin.ec/documentos/informacioneconomica/SectorExterno/ix_TipoCambioReal.html
Periodicidad: Mensual
Instrucción : Estadísticas y Reportes > sección "2. Datos Índice de Tipo de Cambio Real" >
              Descargar Excel "Índice de tipo de cambio real-2018=100".
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader


def extract_fixed_range(start_date: str, end_date: str):
    """Extrae tipo de cambio real entre start_date y end_date (YYYY-MM-DD)."""
    df = bot.download(start=start_date, end=end_date)
    loader.load(df)
    return df


def extract_to_current():
    """Extrae tipo de cambio real desde el inicio del histórico hasta hoy."""
    df = bot.download()
    loader.load(df)
    return df


def extract_to_specific_date(target_date: str):
    """Extrae tipo de cambio real hasta una fecha específica (YYYY-MM-DD)."""
    df = bot.download(end=target_date)
    loader.load(df)
    return df


if __name__ == "__main__":
    extract_to_current()
