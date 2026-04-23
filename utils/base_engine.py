from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_MASTER = {
    "host": "localhost",
    "port": 1433,
    "database": "data_verso",
    "user": "master_user",
    "password": "1234test",
}

DB_READ = {
    "host": "localhost",
    "port": 1433,
    "database": "data_verso",
    "user": "read_user",
    "password": "1234test",
}


def get_master_engine():
    url = (
        f"postgresql+psycopg2://{DB_MASTER['user']}:{DB_MASTER['password']}"
        f"@{DB_MASTER['host']}:{DB_MASTER['port']}/{DB_MASTER['database']}"
    )
    return create_engine(url, echo=False)


def get_read_engine():
    url = (
        f"postgresql+psycopg2://{DB_READ['user']}:{DB_READ['password']}"
        f"@{DB_READ['host']}:{DB_READ['port']}/{DB_READ['database']}"
    )
    return create_engine(url, echo=False)


def get_master_session():
    Session = sessionmaker(bind=get_master_engine())
    return Session()


def get_read_session():
    Session = sessionmaker(bind=get_read_engine())
    return Session()
