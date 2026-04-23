import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.normalizer import clean_dataframe, normalize_numeric

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "recaudacion_mensual"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HIST_START_YEAR = 2018
COLS_NEEDED = ["MES", "PROVINCIA", "VALOR_RECAUDADO"]


def download(start_year: int = None, end_year: int = None) -> pd.DataFrame:
    """Descarga y normaliza la recaudación mensual del SRI por año."""
    s = start_year or HIST_START_YEAR
    e = end_year or datetime.today().year
    frames = []
    for year in range(s, e + 1):
        try:
            df_year = _scrape_year(year)
            df_year = _normalize(df_year)
            df_year["anio"] = year
            frames.append(df_year[COLS_NEEDED + ["anio"]])
        except Exception as ex:
            print(f"[recaudacion_mensual] Error año {year}: {ex}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _scrape_year(year: int) -> pd.DataFrame:
    # TODO: navegar a SRI datasets > Recaudación >
    #       "Valores recaudados mensualmente (provincia y actividad económica)",
    #       seleccionar año, descargar archivo, leer con sep="|".
    raise NotImplementedError(f"Implementar scraping del año {year}")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_dataframe(df)
    df["valor_recaudado"] = normalize_numeric(df["valor_recaudado"])
    return df
