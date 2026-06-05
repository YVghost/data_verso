import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker


def _load_dotenv() -> None:
    """Carga .env de la raíz del proyecto sin depender de python-dotenv."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)


_load_dotenv()

_DRIVER   = "ODBC+Driver+17+for+SQL+Server"
_SERVER   = os.environ.get("DV_SERVER",   "localhost")
_PORT     = int(os.environ.get("DV_PORT", "1433"))
_DATABASE = os.environ.get("DV_DATABASE", "data_verso")

_USE_DOCKER = os.environ.get("DV_USE_DOCKER", "false").strip().lower() == "true"

_ADMIN_USER = os.environ.get("DV_ADMIN_USER",     "")
_ADMIN_PASS = os.environ.get("DV_ADMIN_PASSWORD", "")
_READ_USER  = os.environ.get("DV_READ_USER",      "")
_READ_PASS  = os.environ.get("DV_READ_PASSWORD",  "")


def _build_url(user: str, password: str) -> URL:
    if _USE_DOCKER:
        return URL.create(
            "mssql+pyodbc",
            username=user,
            password=password,
            host=_SERVER,
            port=_PORT,
            database=_DATABASE,
            query={
                "driver": _DRIVER,
                "TrustServerCertificate": "yes",
            },
        )
    # DV_USE_DOCKER=false → Windows Authentication (SQL Server local)
    return URL.create(
        "mssql+pyodbc",
        host=_SERVER,
        database=_DATABASE,
        query={
            "driver": _DRIVER,
            "Trusted_Connection": "yes",
        },
    )


def get_master_engine():
    """Motor con permisos DDL + DML — para los loaders ETL."""
    return create_engine(
        _build_url(_ADMIN_USER, _ADMIN_PASS),
        echo=False,
        fast_executemany=True,
    )


def get_read_engine():
    """Motor de solo lectura — para consultas y exportaciones."""
    return create_engine(
        _build_url(_READ_USER, _READ_PASS),
        echo=False,
    )


def get_master_session():
    Session = sessionmaker(bind=get_master_engine())
    return Session()


def get_read_session():
    Session = sessionmaker(bind=get_read_engine())
    return Session()
