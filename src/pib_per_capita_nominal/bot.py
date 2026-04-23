import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.normalizer import clean_dataframe, normalize_numeric

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "pib_per_capita_nominal"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HIST_START_YEAR = 2000


def download(start_year: int = None, end_year: int = None) -> pd.DataFrame:
    """Descarga, normaliza y filtra el PIB per cápita nominal anual."""
    raw = _scrape()
    df = _normalize(raw)
    return _filter(df, start_year, end_year)


def _scrape() -> pd.DataFrame:
    # TODO: navegar a SectorReal, abrir recuadro PIB per cápita, tres puntos > Serie Histórica,
    #       seleccionar rango 2000-actual, tres rayas > Descargar Excel "pib-per-cpita-nominal".
    raise NotImplementedError("Implementar scraping con Playwright")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_dataframe(df)
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce")
    df["pib_per_capita_usd"] = normalize_numeric(df["pib_per_capita_usd"])
    return df


def _filter(df: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    s = start_year or HIST_START_YEAR
    e = end_year or datetime.today().year
    return df[(df["anio"] >= s) & (df["anio"] <= e)].reset_index(drop=True)
