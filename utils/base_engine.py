from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# SQL Server local — autenticación Windows (Trusted_Connection)
# Estos datos tambien se pueden configurar con variables de entorno
# Si usas autenticación SQL Server, cambia a:
#   mssql+pyodbc://user:password@localhost:1433/data_verso?driver=ODBC+Driver+17+for+SQL+Server
_DRIVER   = "ODBC+Driver+17+for+SQL+Server"
_SERVER   = "localhost"
_DATABASE = "data_verso"
56
_CONN_MASTER = (
    f"mssql+pyodbc://@{_SERVER}/{_DATABASE}"
    f"?driver={_DRIVER}&Trusted_Connection=yes"
)

_CONN_READ = (
    f"mssql+pyodbc://@{_SERVER}/{_DATABASE}"
    f"?driver={_DRIVER}&Trusted_Connection=yes"
)


def get_master_engine():
    return create_engine(_CONN_MASTER, echo=False, fast_executemany=True)


def get_read_engine():
    return create_engine(_CONN_READ, echo=False)


def get_master_session():
    Session = sessionmaker(bind=get_master_engine())
    return Session()


def get_read_session():
    Session = sessionmaker(bind=get_read_engine())
    return Session()
