import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_postgres_connection():
    """Test PostgreSQL database connection"""
    try:
        # Construct database URL
        db_url = (
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
            f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
        )

        # Create SQLAlchemy engine
        engine = create_engine(
            db_url,
            echo=True,  # Enable logging
            pool_pre_ping=True,  # Test connections before using them
            connect_args={
                'connect_timeout': 10  # Set connection timeout
            }
        )

        # Test connection
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✅ PostgreSQL Connection Successful!")
            return True
    except Exception as e:
        print(f"❌ PostgreSQL Connection Failed: {e}")
        return False

def test_redis_connection():
    """Test Redis connection"""
    try:
        # Create Redis client
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST'),
            port=int(os.getenv('REDIS_PORT')),
            db=int(os.getenv('REDIS_DB'))
        )

        # Test connection
        redis_client.ping()
        print("✅ Redis Connection Successful!")
        return True
    except Exception as e:
        print(f"❌ Redis Connection Failed: {e}")
        return False

def main():
    print("Testing Database Connections...")
    postgres_status = test_postgres_connection()
    redis_status = test_redis_connection()

    if postgres_status and redis_status:
        print("\n🎉 All Connections Successful!")
    else:
        print("\n⚠️ Some Connections Failed. Check your configuration.")

if __name__ == "__main__":
    main()