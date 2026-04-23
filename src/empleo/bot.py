import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.normalizer import clean_dataframe, normalize_numeric, normalize_date_column

DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "empleo"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HIST_START = datetime(2007, 1, 1)


def download(start: str = None, end: str = None) -> pd.DataFrame:
    """Descarga, normaliza y filtra los datos de empleo ENEMDU."""
    raw = _scrape()
    df = _normalize(raw)
    return _filter(df, start, end)


def _scrape() -> pd.DataFrame:
    # TODO: navegar a INEC ENEMDU Trimestral, clic en panel azul > ENEMDU Trimestral,
    #       descargar "202602_Tabulados_Mercado_Laboral_EXCEL", leer hoja "1. Poblaciones".
    raise NotImplementedError("Implementar scraping con Playwright")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_dataframe(df)
    df["fecha"] = normalize_date_column(df["fecha"])
    for col in ["poblacion_total", "pea", "empleados", "desempleados"]:
        if col in df.columns:
            df[col] = normalize_numeric(df[col])
    return df


def _filter(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    start_dt = datetime.strptime(start, "%Y-%m-%d") if start else HIST_START
    end_dt = datetime.strptime(end, "%Y-%m-%d") if end else datetime.today()
    return df[(df["fecha"] >= start_dt) & (df["fecha"] <= end_dt)].reset_index(drop=True)
