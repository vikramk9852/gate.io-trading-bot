from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class Database:
    def __init__(self, secret_config):
        self.user = secret_config['db_user']
        self.port = secret_config['db_port']
        self.dbname = secret_config['db_name']
        self.host = secret_config['db_host']
        self.password = secret_config['db_password']
        self.engine = None

        database_uri = f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"
        engine = create_engine(database_uri)
        self.engine = engine
        self.session = sessionmaker(bind=self.engine)

