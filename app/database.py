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
    
    # Create conversations collection if it doesn't exist
    if "conversations" not in existing_collections:
        await database.create_collection("conversations")
        print("✅ Created conversations collection")
    
    # Create messages collection if it doesn't exist
    if "messages" not in existing_collections:
        await database.create_collection("messages")
        print("✅ Created messages collection")
    
    # Create groups collection if it doesn't exist
    if "groups" not in existing_collections:
        await database.create_collection("groups")
        print("✅ Created groups collection")
        print("✅ Created messages collection")
    
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
        
        # Create indexes on conversations collection
        # Index 1: Index on participants - Fast conversation lookup
        await database["conversations"].create_index(
            "participants",
            name="conversation_participants_idx"
        )
        print("✅ Created index on conversations.participants")
        
        # Index 2: Index on last_message_at - Fast sorting for inbox
        await database["conversations"].create_index(
            "last_message_at",
            name="conversation_last_message_idx"
        )
        print("✅ Created index on conversations.last_message_at")
        
        # Create indexes on messages collection
        # Index 1: Index on conversation_id - Fast message retrieval
        await database["messages"].create_index(
            "conversation_id",
            name="message_conversation_idx"
        )
        print("✅ Created index on messages.conversation_id")
        
        # Index 2: Compound index on (conversation_id, created_at) - Fast sorted messages
        await database["messages"].create_index(
            [("conversation_id", 1), ("created_at", -1)],
            name="message_conversation_time_idx"
        )
        print("✅ Created compound index on messages.(conversation_id, created_at)")
        
        # Index 3: Compound index on (conversation_id, is_read) - Fast unread count
        await database["messages"].create_index(
            [("conversation_id", 1), ("is_read", 1)],
            name="message_conversation_read_idx"
        )
        print("✅ Created compound index on messages.(conversation_id, is_read)")
        
    except Exception as e:
        print(f"⚠️ Index creation note: {e}")
    
    # Create indexes on groups collection
    try:
        # Index 1: Index on members - Fast group lookup for user
        await database["groups"].create_index(
            "members",
            name="group_members_idx"
        )
        print("✅ Created index on groups.members")
        
        # Index 2: Index on last_message_at - Fast sorting for group list
        await database["groups"].create_index(
            "last_message_at",
            name="group_last_message_idx"
        )
        print("✅ Created index on groups.last_message_at")
        
        # Index 3: Index on created_by - Fast creator lookup
        await database["groups"].create_index(
            "created_by",
            name="group_creator_idx"
        )
        print("✅ Created index on groups.created_by")
        
        # Index 4: Index on admins - Fast admin lookup
        await database["groups"].create_index(
            "admins",
            name="group_admins_idx"
        )
        print("✅ Created index on groups.admins")
        
    except Exception as e:
        print(f"⚠️ Group index creation note: {e}")
    
    # Create company collection (single document for company info)
    try:
        if "company" not in existing_collections:
            await database.create_collection("company")
            print("✅ Created company collection")
        
        # Check if company document exists, if not create default
        # Use upsert with unique constraint to prevent race condition
        from datetime import datetime
        result = await database["company"].update_one(
            {},  # Match any document
            {
                "$setOnInsert": {  # Only set these if inserting new document
                    "company_name": "Your Company Name",
                    "company_logo_url": None,
                    "company_description": None,
                    "company_address": None,
                    "company_city": None,
                    "company_state": None,
                    "company_country": None,
                    "company_pincode": None,
                    "company_website": None,
                    "company_industry": None,
                    "company_founded_year": None,
                    "company_size": None,
                    "company_gst_number": None,
                    "company_pan_number": None,
                    "is_active": True,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True  # Create if doesn't exist
        )
        
        if result.upserted_id:
            print("✅ Created default company document")
        else:
            print("✅ Company document already exists")
            
        # Ensure only one company document exists (cleanup if multiple)
        company_count = await database["company"].count_documents({})
        if company_count > 1:
            print(f"⚠️ Found {company_count} company documents, keeping only the first one")
            # Keep the first document, delete others
            first_company = await database["company"].find_one({})
            await database["company"].delete_many({"_id": {"$ne": first_company["_id"]}})
            print("✅ Cleaned up duplicate company documents")
            
    except Exception as e:
        print(f"⚠️ Company collection creation note: {e}")
    
    print("✅ Collections and indexes initialized")
