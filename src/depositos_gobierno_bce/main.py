"""
Fuente  : BCE - Depósitos Gobierno Central en BCE
URL     : https://contenido.bce.fin.ec/documentos/informacioneconomica/MonetarioFinanciero/ix_ReportesMonetarios.html
Periodicidad: Semanal por año
Instrucción : Estadísticas y Reportes > Reporte Monetario Semanal > elegir año > elegir semana >
              descargar "InfMonetariaSemanal_DDMMYYYY.xls", hoja "IMS5".
              Filas clave: 63 (Dep. transferibles GC), 74 (Gobierno Central),
              79-80 (Otros depósitos GC).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import bot
import loader


def extract_fixed_range(start_year: int, end_year: int):
    """Extrae depósitos del gobierno central entre start_year y end_year."""
    df = bot.download(start_year=start_year, end_year=end_year)
    loader.load(df)
    return df


def extract_to_current():
    """Extrae depósitos del gobierno central desde 2012 hasta hoy."""
    df = bot.download()
    loader.load(df)
    return df


def extract_to_specific_date(target_year: int):
    """Extrae depósitos del gobierno central desde 2012 hasta target_year."""
    df = bot.download(end_year=target_year)
    loader.load(df)
    return df


if __name__ == "__main__":
    extract_to_current()
