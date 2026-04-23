import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.normalizer import clean_dataframe, normalize_numeric, normalize_date_column

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "tipo_de_cambio"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HIST_START = datetime(2000, 1, 1)


def download(start: str = None, end: str = None) -> pd.DataFrame:
    """Descarga, normaliza y filtra el índice de tipo de cambio real mensual."""
    raw = _scrape()
    df = _normalize(raw)
    return _filter(df, start, end)


def _scrape() -> pd.DataFrame:
    # TODO: navegar a BCE > TipoCambioReal > Estadísticas y Reportes >
    #       sección "2. Datos Índice de Tipo de Cambio Real",
    #       descargar Excel "Índice de tipo de cambio real-2018=100".
    #       El Excel contiene una columna por país/moneda — hacer melt a formato largo.
    raise NotImplementedError("Implementar scraping con Playwright")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_dataframe(df)
    df["fecha"] = normalize_date_column(df["fecha"])
    df["indice_tcr"] = normalize_numeric(df["indice_tcr"])
    return df


def _filter(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    start_dt = datetime.strptime(start, "%Y-%m-%d") if start else HIST_START
    end_dt = datetime.strptime(end, "%Y-%m-%d") if end else datetime.today()
    return df[(df["fecha"] >= start_dt) & (df["fecha"] <= end_dt)].reset_index(drop=True)
