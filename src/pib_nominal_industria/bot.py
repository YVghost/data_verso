import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.normalizer import clean_dataframe, normalize_numeric

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "pib_nominal_industria"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HIST_START_YEAR = 1990


def download(start_year: int = None, end_year: int = None) -> pd.DataFrame:
    """Descarga, normaliza y filtra el PIB nominal por industria trimestral."""
    raw = _scrape()
    df = _normalize(raw)
    return _filter(df, start_year, end_year)


def _scrape() -> pd.DataFrame:
    # TODO: mismo flujo que pib_nominal (mismo Excel "PUB - PIB Trimestral", hoja "SeriesCT1")
    #       pero reteniendo columnas: Año, Trimestre, Nombre Industria, Miles USD Constantes.
    raise NotImplementedError("Implementar scraping con Playwright")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_dataframe(df)
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce")
    df["trimestre"] = pd.to_numeric(df["trimestre"], errors="coerce")
    df["miles_usd_constantes"] = normalize_numeric(df["miles_usd_constantes"])
    return df


def _filter(df: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    s = start_year or HIST_START_YEAR
    e = end_year or datetime.today().year
    return df[(df["anio"] >= s) & (df["anio"] <= e)].reset_index(drop=True)
