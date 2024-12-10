from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Create MetaData objects for each schema
auth_meta = MetaData(schema='auth')
organization_meta = MetaData(schema='organization')
cluster_meta = MetaData(schema='cluster')

# Create base classes for each schema
AuthBase = declarative_base(metadata=auth_meta)
OrganizationBase = declarative_base(metadata=organization_meta)
ClusterBase = declarative_base(metadata=cluster_meta)

# Database URL
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"

# Create engine
engine = create_engine(DATABASE_URL, echo=True)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create schemas and tables
def create_schemas():
    # Create schemas
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS cluster;"))
        conn.commit()

    # Create all tables
    auth_meta.create_all(bind=engine)
    organization_meta.create_all(bind=engine)
    cluster_meta.create_all(bind=engine)