import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Load environment variables
load_dotenv()

# Create Base class
Base = declarative_base()

# Database URL
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=True,
    future=True
)

def init_db():
    """Initialize database schemas and tables"""
    # Import models
    from backend_service.models.auth import User
    from backend_service.models.organisation import Organization, OrganizationMember
    from backend_service.models.cluster import Cluster, Deployment

    # Create schemas
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS organization;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS cluster;"))
        conn.commit()
    print("Created schemas")

    # Get inspector
    inspector = inspect(engine)

    # Create tables
    models = [User, Organization, OrganizationMember, Cluster, Deployment]

    for Model in models:
        schema = Model.__table_args__['schema']
        table_name = Model.__tablename__

        # Check if table exists
        if not inspector.has_table(table_name, schema=schema):
            try:
                Model.__table__.create(engine)
                print(f"Created table {schema}.{table_name}")
            except Exception as e:
                print(f"Error creating table {Model.__name__}: {e}")
        else:
            print(f"Table {schema}.{table_name} already exists")

if __name__ == "__main__":
    print("Creating database schemas and tables...")
    init_db()
    print("Database initialization completed!")