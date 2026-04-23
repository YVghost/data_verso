import re
import unicodedata
import pandas as pd


def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.strip().upper()
    return text


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [
        re.sub(r"\s+", "_", normalize_text(str(c))).strip("_")
        for c in df.columns
    ]
    return df


def normalize_numeric(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace(r"[^\d\.\-]", "", regex=True)
        .replace("", pd.NA)
        .astype(float)
    )


def normalize_date_column(series: pd.Series, dayfirst: bool = False) -> pd.Series:
    return pd.to_datetime(series, dayfirst=dayfirst, errors="coerce")


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(how="all").reset_index(drop=True)
    df = normalize_column_names(df)
    return df
