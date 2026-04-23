"""
Fuente  : BCE - Reservas Internacionales
URL     : https://contenido.bce.fin.ec/documentos/informacioneconomica/MonetarioFinanciero/ix_ReservasInternacionales.html
Periodicidad: Mensual
Instrucción : Estadísticas y Reportes > Serie de Reservas Internacionales >
              Excel "Serie Reservas Internacionales" > archivo "ReservasInternacionales" >
              hoja "Mensual 2000 ene-2026", columna RI (1+2+3+4+5+6).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader


def extract_fixed_range(start_date: str, end_date: str):
    """Extrae reservas internacionales entre start_date y end_date (YYYY-MM-DD)."""
    df = bot.download(start=start_date, end=end_date)
    loader.load(df)
    return df


def extract_to_current():
    """Extrae reservas internacionales desde enero 2000 hasta hoy."""
    df = bot.download()
    loader.load(df)
    return df


def extract_to_specific_date(target_date: str):
    """Extrae reservas internacionales hasta una fecha específica (YYYY-MM-DD)."""
    df = bot.download(end=target_date)
    loader.load(df)
    return df


if __name__ == "__main__":
    extract_to_current()
