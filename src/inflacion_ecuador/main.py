"""
Fuente  : INEC - Índice de Precios al Consumidor (IPC)
URL     : https://www.ecuadorencifras.gob.ec/indice-de-precios-al-consumidor/
Periodicidad: Mensual (serie histórica desde 1969)
Instrucción : Descargar ZIP desde "Tabulados y series históricas" > botón Excel,
              abrir "SERIE HISTORICA IPC_*.xls", pestaña 2 (variación mensual IPC).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader


def extract_fixed_range(start_date: str, end_date: str):
    """Extrae variación mensual del IPC entre start_date y end_date (YYYY-MM-DD)."""
    df = bot.download(start=start_date, end=end_date)
    loader.load(df)
    return df


def extract_to_current():
    """Extrae variación mensual del IPC desde el inicio del histórico hasta hoy."""
    df = bot.download()
    loader.load(df)
    return df


def extract_to_specific_date(target_date: str):
    """Extrae variación mensual del IPC hasta una fecha específica (YYYY-MM-DD)."""
    df = bot.download(end=target_date)
    loader.load(df)
    return df


if __name__ == "__main__":
    extract_to_current()
