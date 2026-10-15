import os
from functools import lru_cache

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv(
    "MONGODB_DATABASE",
    "climate_hazards",
)


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    """Create the MongoDB client only when it is first needed."""
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI is not configured")

    return MongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )


def get_database():
    """Return the configured MongoDB database."""
    return get_client()[MONGODB_DATABASE]


def check_mongodb_connection() -> bool:
    """Verify connectivity to MongoDB."""
    get_client().admin.command("ping")
    return True
