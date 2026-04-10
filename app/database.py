"""
MongoDB database connection management using Motor (async driver).
This file creates a connection to MongoDB and provides access to the database.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings
from typing import Optional


class Database:
    """
    Database connection manager.
    Handles connecting to MongoDB and providing access to collections.
    """
    
    client: Optional[AsyncIOMotorClient] = None
    database: Optional[AsyncIOMotorDatabase] = None


# Create a single instance of Database
db = Database()


async def connect_to_mongo():
    """
    Connect to MongoDB when the application starts.
    This function is called once during startup.
    """
    print(f"🔌 Connecting to MongoDB at {settings.MONGODB_URL}...")
    
    # Create MongoDB client
    db.client = AsyncIOMotorClient(settings.MONGODB_URL)
    
    # Get the database (creates it if doesn't exist)
    db.database = db.client[settings.DATABASE_NAME]
    
    print(f"✅ Connected to database: {settings.DATABASE_NAME}")
    
    # Initialize collections and indexes
    await initialize_collections()


async def close_mongo_connection():
    """
    Close MongoDB connection when the application shuts down.
    This function is called once during shutdown.
    """
    print("🔌 Closing MongoDB connection...")
    
    if db.client:
        db.client.close()
    
    print("✅ MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """
    Get the database instance.
    This function is used throughout the app to access MongoDB collections.
    
    Returns:
        AsyncIOMotorDatabase: The MongoDB database instance
    """
    return db.database
