import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import urllib.parse

def diagnose_postgres_connection():
    print("🔍 PostgreSQL Connection Diagnostics")
    print("-" * 50)

    # Gather environment variables
    env_vars = [
        'DB_USER', 'DB_PASSWORD', 'DB_HOST',
        'DB_PORT', 'DB_NAME', 'DATABASE_URL'
    ]

    print("📋 Environment Variables:")
    for var in env_vars:
        value = os.getenv(var, 'NOT SET')
        # Mask password
        if 'PASSWORD' in var:
            value = value[:2] + '*' * (len(value) - 2) if value != 'NOT SET' else value
        print(f"{var}: {value}")

    # Attempt to construct connection URL
    try:
        user = os.getenv('DB_USER')
        password = os.getenv('DB_PASSWORD')
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME')

        # URL encode password to handle special characters
        encoded_password = urllib.parse.quote_plus(password) if password else ''

        # Construct database URL
        database_url = f'postgresql://{user}:{encoded_password}@{host}:{port}/{db_name}'

        print("\n🔗 Constructed Database URL:")
        # Mask password in printed URL
        masked_url = database_url.replace(encoded_password, '*' * len(encoded_password))
        print(masked_url)

    except Exception as e:
        print(f"❌ Error constructing URL: {e}")
        return False

    # Try SQLAlchemy connection
    try:
        # Create engine with additional diagnostic parameters
        engine = create_engine(
            database_url,
            echo=True,  # Enable logging
            pool_pre_ping=True,  # Test connections before using them
            connect_args={
                'connect_timeout': 10  # Set connection timeout
            }
        )

        # Attempt to connect and execute a simple query
        with engine.connect() as connection:
            # Use text() to create a safe SQL statement
            result = connection.execute(text("SELECT 1"))

            # Fetch the result
            fetch_result = result.fetchone()

            print("\n✅ Connection Successful!")
            print(f"Test Query Result: {fetch_result}")
            return True

    except SQLAlchemyError as e:
        print("\n❌ SQLAlchemy Connection Error:")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Details: {e}")

        # Provide specific diagnostics based on error type
        if 'OperationalError' in str(type(e)):
            print("\n🕵️ Possible Causes:")
            print("1. Database server not running")
            print("2. Incorrect host/port")
            print("3. Firewall blocking connection")
            print("4. Incorrect credentials")

        return False
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        return False

def main():
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Run diagnostic
    success = diagnose_postgres_connection()

    # Exit with appropriate status
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()