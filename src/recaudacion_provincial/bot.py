import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.normalizer import clean_dataframe, normalize_numeric

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "recaudacion_provincial"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HIST_START_YEAR = 2018


def download(start_year: int = None, end_year: int = None) -> pd.DataFrame:
    """Descarga y normaliza la recaudación provincial del SRI, agrupada por año y provincia."""
    s = start_year or HIST_START_YEAR
    e = end_year or datetime.today().year
    frames = []
    for year in range(s, e + 1):
        try:
            df_year = _scrape_year(year)
            df_year = _normalize(df_year)
            df_year["anio"] = year
            df_grouped = (
                df_year.groupby(["provincia", "anio"], as_index=False)["valor_recaudado"]
                .sum()
            )
            frames.append(df_grouped)
        except Exception as ex:
            print(f"[recaudacion_provincial] Error año {year}: {ex}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _scrape_year(year: int) -> pd.DataFrame:
    # TODO: mismo archivo que recaudacion_mensual (sep="|"),
    #       retener columnas PROVINCIA y VALOR_RECAUDADO para agrupar.
    raise NotImplementedError(f"Implementar scraping del año {year}")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_dataframe(df)
    df["valor_recaudado"] = normalize_numeric(df["valor_recaudado"])
    return df
