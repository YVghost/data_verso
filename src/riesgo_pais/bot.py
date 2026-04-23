import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.normalizer import clean_dataframe, normalize_numeric, normalize_date_column

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "riesgo_pais"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HIST_START = datetime(2004, 1, 1)


def download(start: str = None, end: str = None) -> pd.DataFrame:
    """Descarga, normaliza y filtra el riesgo país (EMBI) histórico."""
    raw = _scrape()
    df = _normalize(raw)
    return _filter(df, start, end)


def _scrape() -> pd.DataFrame:
    # TODO: navegar a BCE > SectorExterno > sección inferior Riesgo País,
    #       tres puntos izquierdos > Serie Histórica > nueva pestaña,
    #       tres líneas superiores > Descargar Excel "riesgo-pas".
    raise NotImplementedError("Implementar scraping con Playwright")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_dataframe(df)
    df["fecha"] = normalize_date_column(df["fecha"])
    df["embi_puntos"] = normalize_numeric(df["embi_puntos"])
    return df


def _filter(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    start_dt = datetime.strptime(start, "%Y-%m-%d") if start else HIST_START
    end_dt = datetime.strptime(end, "%Y-%m-%d") if end else datetime.today()
    return df[(df["fecha"] >= start_dt) & (df["fecha"] <= end_dt)].reset_index(drop=True)
