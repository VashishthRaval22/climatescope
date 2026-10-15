
from app.database import (
    MONGODB_DATABASE,
    check_mongodb_connection,
)


def main():
    try:
        check_mongodb_connection()
        print("MongoDB connection successful!")
        print(f"Database configured: {MONGODB_DATABASE}")
    except Exception as exc:
        print(f"MongoDB connection failed: {type(exc).__name__}")
        print("Check your Atlas URI, database credentials, and network access.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
