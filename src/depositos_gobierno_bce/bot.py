import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.normalizer import clean_dataframe, normalize_numeric, normalize_date_column

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "depositos_gobierno_bce"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HIST_START_YEAR = 2012

# Filas de la hoja IMS5 que contienen depósitos del Gobierno Central
ROWS_GC = {
    "dep_transferibles_63": 63,
    "dep_transferibles_74": 74,
    "gc_74": 74,
    "otros_depositos_gc_80": 80,
}


def download(start_year: int = None, end_year: int = None) -> pd.DataFrame:
    """Descarga y normaliza depósitos del Gobierno Central en BCE (semanal por año)."""
    s = start_year or HIST_START_YEAR
    e = end_year or datetime.today().year
    frames = []
    for year in range(s, e + 1):
        try:
            df_year = _scrape_year(year)
            df_year = _normalize(df_year)
            frames.append(df_year)
        except Exception as ex:
            print(f"[depositos_gobierno_bce] Error año {year}: {ex}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _scrape_year(year: int) -> pd.DataFrame:
    # TODO: navegar a BCE > Estadísticas y Reportes > Reporte Monetario Semanal > año,
    #       iterar cada semana disponible, descargar "InfMonetariaSemanal_*.xls",
    #       leer hoja "IMS5", extraer filas 63, 74, 79, 80 como columnas.
    raise NotImplementedError(f"Implementar scraping semanas del año {year}")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_dataframe(df)
    df["fecha_semana"] = normalize_date_column(df["fecha_semana"])
    for col in ["dep_transferibles_gc", "otros_depositos_gc"]:
        if col in df.columns:
            df[col] = normalize_numeric(df[col])
    return df
