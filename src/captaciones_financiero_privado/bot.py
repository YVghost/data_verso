import sys
import zipfile
import pandas as pd
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.normalizer import clean_dataframe, normalize_numeric

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "captaciones_financiero_privado"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HIST_START_YEAR = 2014


def download(start_year: int = None, end_year: int = None) -> pd.DataFrame:
    """Descarga y normaliza captaciones del sistema financiero privado por año."""
    s = start_year or HIST_START_YEAR
    e = end_year or datetime.today().year
    frames = []
    for year in range(s, e + 1):
        try:
            df_year = _scrape_year(year)
            df_year = _normalize(df_year)
            df_year["anio"] = year
            frames.append(df_year)
        except Exception as ex:
            print(f"[captaciones_financiero_privado] Error año {year}: {ex}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _scrape_year(year: int) -> pd.DataFrame:
    # TODO: navegar a Superbancos, localizar carpeta ZIP del año,
    #       entrar a carpeta captaciones, descargar ZIP,
    #       extraer "BANCOS PRIVADOS - CAPTACIONES ENE - DIC {year}.xlsx".
    raise NotImplementedError(f"Implementar scraping del año {year}")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_dataframe(df)
    if "total_depositos" in df.columns:
        df["total_depositos"] = normalize_numeric(df["total_depositos"])
    return df
