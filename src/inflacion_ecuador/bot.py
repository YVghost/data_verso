import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.normalizer import clean_dataframe, normalize_numeric, normalize_date_column

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "inflacion_ecuador"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HIST_START = datetime(1969, 1, 1)


def download(start: str = None, end: str = None) -> pd.DataFrame:
    """Descarga, normaliza y filtra la variación mensual del IPC."""
    raw = _scrape()
    df = _normalize(raw)
    return _filter(df, start, end)


def _scrape() -> pd.DataFrame:
    # TODO: abrir página INEC, clic en botón Excel de "Tabulados y series históricas",
    #       descargar ZIP, extraer "SERIE HISTORICA IPC_*.xls", leer pestaña 2.
    raise NotImplementedError("Implementar scraping con Playwright")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_dataframe(df)
    df["fecha"] = normalize_date_column(df["fecha"])
    df["variacion_mensual"] = normalize_numeric(df["variacion_mensual"])
    return df


def _filter(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    start_dt = datetime.strptime(start, "%Y-%m-%d") if start else HIST_START
    end_dt = datetime.strptime(end, "%Y-%m-%d") if end else datetime.today()
    return df[(df["fecha"] >= start_dt) & (df["fecha"] <= end_dt)].reset_index(drop=True)
