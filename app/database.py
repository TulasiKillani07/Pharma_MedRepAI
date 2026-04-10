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


async def initialize_collections():
    """
    Initialize collections and create indexes for optimal performance.
    This function is called once during startup after connecting to MongoDB.
    """
    database = get_database()
    
    print("🔧 Initializing collections and indexes...")
    
    # Create post_likes collection if it doesn't exist
    existing_collections = await database.list_collection_names()
    if "post_likes" not in existing_collections:
        await database.create_collection("post_likes")
        print("✅ Created post_likes collection")
    
    # Create post_comments collection if it doesn't exist
    if "post_comments" not in existing_collections:
        await database.create_collection("post_comments")
        print("✅ Created post_comments collection")
    
    # Create connections collection if it doesn't exist
    if "connections" not in existing_collections:
        await database.create_collection("connections")
        print("✅ Created connections collection")
    
    # Create indexes on post_likes collection
    try:
        # Index 1: Compound index on (post_id, user_id) - Prevents duplicate likes
        await database["post_likes"].create_index(
            [("post_id", 1), ("user_id", 1)],
            unique=True,
            name="post_user_unique_idx"
        )
        print("✅ Created compound index on (post_id, user_id)")
        
        # Index 2: Index on post_id - Fast retrieval of all likes for a post
        await database["post_likes"].create_index(
            "post_id",
            name="post_id_idx"
        )
        print("✅ Created index on post_id")
        
        # Index 3: Index on user_id - Fast retrieval of all posts liked by a user
        await database["post_likes"].create_index(
            "user_id",
            name="user_id_idx"
        )
        print("✅ Created index on user_id")
        
        # Create indexes on post_comments collection
        # Index 1: Index on post_id - Fast retrieval of all comments for a post
        await database["post_comments"].create_index(
            "post_id",
            name="comment_post_id_idx"
        )
        print("✅ Created index on post_comments.post_id")
        
        # Index 2: Index on author_id - Fast retrieval of all comments by a user
        await database["post_comments"].create_index(
            "author_id",
            name="comment_author_id_idx"
        )
        print("✅ Created index on post_comments.author_id")
        
        # Index 3: Compound index on (post_id, is_active) - Fast retrieval of active comments
        await database["post_comments"].create_index(
            [("post_id", 1), ("is_active", 1)],
            name="comment_post_active_idx"
        )
        print("✅ Created compound index on post_comments.(post_id, is_active)")
        
        # Create indexes on connections collection
        # Index 1: Compound index on (requester_id, receiver_id) - Prevent duplicates
        await database["connections"].create_index(
            [("requester_id", 1), ("receiver_id", 1)],
            unique=True,
            name="connection_unique_idx"
        )
        print("✅ Created compound unique index on connections.(requester_id, receiver_id)")
        
        # Index 2: Compound index on (receiver_id, status) - Fast pending requests
        await database["connections"].create_index(
            [("receiver_id", 1), ("status", 1)],
            name="connection_receiver_status_idx"
        )
        print("✅ Created compound index on connections.(receiver_id, status)")
        
        # Index 3: Compound index on (requester_id, status) - Fast sent requests
        await database["connections"].create_index(
            [("requester_id", 1), ("status", 1)],
            name="connection_requester_status_idx"
        )
        print("✅ Created compound index on connections.(requester_id, status)")
        
        # Index 4: Index on requester_id
        await database["connections"].create_index(
            "requester_id",
            name="connection_requester_idx"
        )
        print("✅ Created index on connections.requester_id")
        
        # Index 5: Index on receiver_id
        await database["connections"].create_index(
            "receiver_id",
            name="connection_receiver_idx"
        )
        print("✅ Created index on connections.receiver_id")
        
    except Exception as e:
        print(f"⚠️ Index creation note: {e}")
    
    print("✅ Collections and indexes initialized")
