from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from .config import settings

# SQLALCHEMY_DATABASE_URL= 'postgresql://<username>:<password>@<ip-address/hostname>:<database_port>/<databse_name>'
SQLALCHEMY_DATABASE_URL=f'postgresql://{settings.database_username}:{settings.database_password}@{settings.database_hostname}:{settings.database_port}/{settings.database_name}'
engine=create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal=sessionmaker(autoflush=False,autocommit=False,bind=engine) #responsible to talk to our databases
base=declarative_base()
def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()