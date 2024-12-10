import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """
    Application configuration settings
    """
    # Project details
    PROJECT_NAME: str = "Backend Cluster Service"

    # Database configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost/backendservice"
    )

    # Security settings
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "your-secret-key-change-in-production"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS settings
    ALLOWED_HOSTS: List[str] = [
        "http://localhost",
        "http://localhost:8000",
        "https://localhost",
        "https://localhost:8000"
    ]

    # Redis configuration
    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        "redis://localhost:6379/0"
    )

# Create a singleton settings object
settings = Settings()