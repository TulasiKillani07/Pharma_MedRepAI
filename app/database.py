"""
MongoDB database connection management using Motor (async driver).
This file creates a connection to MongoDB and provides access to the database.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings
from app.utils.logger import get_medrep_logger
from typing import Optional

# Initialize logger
logger = get_medrep_logger(__name__)


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
    logger.info(f"Connecting to MongoDB at {settings.MONGODB_URL}")
    
    try:
        # Create MongoDB client
        db.client = AsyncIOMotorClient(settings.MONGODB_URL)
        
        # Get the database (creates it if doesn't exist)
        db.database = db.client[settings.DATABASE_NAME]
        
        logger.info(f"Connected to database: {settings.DATABASE_NAME}")
        
        # Initialize collections and indexes
        await initialize_collections()
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}", exc_info=True)
        raise


async def close_mongo_connection():
    """
    Close MongoDB connection when the application shuts down.
    This function is called once during shutdown.
    """
    logger.info("Closing MongoDB connection")
    
    if db.client:
        db.client.close()
    
    logger.info("MongoDB connection closed")


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
    
    logger.info("Initializing collections and indexes...")
    
    # Create post_likes collection if it doesn't exist
    existing_collections = await database.list_collection_names()
    if "post_likes" not in existing_collections:
        await database.create_collection("post_likes")
    
    # Create post_comments collection if it doesn't exist
    if "post_comments" not in existing_collections:
        await database.create_collection("post_comments")
    
    # Create connections collection if it doesn't exist
    if "connections" not in existing_collections:
        await database.create_collection("connections")
    
    # Create conversations collection if it doesn't exist
    if "conversations" not in existing_collections:
        await database.create_collection("conversations")    
    # Create messages collection if it doesn't exist
    if "messages" not in existing_collections:
        await database.create_collection("messages")    
    # Create groups collection if it doesn't exist
    if "groups" not in existing_collections:
        await database.create_collection("groups")    
    # Create indexes on post_likes collection
    try:
        # Index 1: Compound index on (post_id, user_id) - Prevents duplicate likes
        await database["post_likes"].create_index(
            [("post_id", 1), ("user_id", 1)],
            unique=True,
            name="post_user_unique_idx"
        )        
        # Index 2: Index on post_id - Fast retrieval of all likes for a post
        await database["post_likes"].create_index(
            "post_id",
            name="post_id_idx"
        )        
        # Index 3: Index on user_id - Fast retrieval of all posts liked by a user
        await database["post_likes"].create_index(
            "user_id",
            name="user_id_idx"
        )        
        # Create indexes on post_comments collection
        # Index 1: Index on post_id - Fast retrieval of all comments for a post
        await database["post_comments"].create_index(
            "post_id",
            name="comment_post_id_idx"
        )        
        # Index 2: Index on author_id - Fast retrieval of all comments by a user
        await database["post_comments"].create_index(
            "author_id",
            name="comment_author_id_idx"
        )        
        # Index 3: Compound index on (post_id, is_active) - Fast retrieval of active comments
        await database["post_comments"].create_index(
            [("post_id", 1), ("is_active", 1)],
            name="comment_post_active_idx"
        )        
        # Create indexes on connections collection
        # Index 1: Compound index on (requester_id, receiver_id) - Prevent duplicates
        await database["connections"].create_index(
            [("requester_id", 1), ("receiver_id", 1)],
            unique=True,
            name="connection_unique_idx"
        )        
        # Index 2: Compound index on (receiver_id, status) - Fast pending requests
        await database["connections"].create_index(
            [("receiver_id", 1), ("status", 1)],
            name="connection_receiver_status_idx"
        )        
        # Index 3: Compound index on (requester_id, status) - Fast sent requests
        await database["connections"].create_index(
            [("requester_id", 1), ("status", 1)],
            name="connection_requester_status_idx"
        )        
        # Index 4: Index on requester_id
        await database["connections"].create_index(
            "requester_id",
            name="connection_requester_idx"
        )        
        # Index 5: Index on receiver_id
        await database["connections"].create_index(
            "receiver_id",
            name="connection_receiver_idx"
        )        
        # Create indexes on conversations collection
        # Index 1: Index on participants - Fast conversation lookup
        await database["conversations"].create_index(
            "participants",
            name="conversation_participants_idx"
        )        
        # Index 2: Index on last_message_at - Fast sorting for inbox
        await database["conversations"].create_index(
            "last_message_at",
            name="conversation_last_message_idx"
        )        
        # Create indexes on messages collection
        # Index 1: Index on conversation_id - Fast message retrieval
        await database["messages"].create_index(
            "conversation_id",
            name="message_conversation_idx"
        )        
        # Index 2: Compound index on (conversation_id, created_at) - Fast sorted messages
        await database["messages"].create_index(
            [("conversation_id", 1), ("created_at", -1)],
            name="message_conversation_time_idx"
        )        
        # Index 3: Compound index on (conversation_id, is_read) - Fast unread count
        await database["messages"].create_index(
            [("conversation_id", 1), ("is_read", 1)],
            name="message_conversation_read_idx"
        )        
    except Exception as e:        
        logger.warning(f"Index creation issue: {e}")        
    # Create groups collection if it doesn't exist
    try:
        if "groups" not in existing_collections:
            await database.create_collection("groups")        
        # Index 1: Index on members - Fast group lookup for user
        await database["groups"].create_index(
            "members",
            name="group_members_idx"
        )        
        # Index 2: Index on last_message_at - Fast sorting for group list
        await database["groups"].create_index(
            "last_message_at",
            name="group_last_message_idx"
        )        
        # Index 3: Index on created_by - Fast creator lookup
        await database["groups"].create_index(
            "created_by",
            name="group_creator_idx"
        )        
        # Index 4: Index on admins - Fast admin lookup
        await database["groups"].create_index(
            "admins",
            name="group_admins_idx"
        )        
    except Exception as e:        
        logger.warning(f"Index creation issue: {e}")        
    # Create notifications collection if it doesn't exist
    try:
        if "notifications" not in existing_collections:
            await database.create_collection("notifications")        
        # Index 1: Compound index on (user_id, created_at) - Fast user notifications sorted by time
        await database["notifications"].create_index(
            [("user_id", 1), ("created_at", -1)],
            name="notification_user_time_idx"
        )        
        # Index 2: Compound index on (user_id, is_read) - Fast unread count
        await database["notifications"].create_index(
            [("user_id", 1), ("is_read", 1)],
            name="notification_user_read_idx"
        )        
        # Index 3: TTL index on expires_at - Auto-delete expired notifications
        await database["notifications"].create_index(
            "expires_at",
            name="notification_expires_idx",
            expireAfterSeconds=0
        )        
    except Exception as e:        
        logger.warning(f"Index creation issue: {e}")        
    # Create company collection (single document for company info)
    try:
        if "company" not in existing_collections:
            await database.create_collection("company")        
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
            pass
        else:
            pass
            
        # Ensure only one company document exists (cleanup if multiple)
        company_count = await database["company"].count_documents({})
        if company_count > 1:
            # Keep the first document, delete others
            first_company = await database["company"].find_one({})
            await database["company"].delete_many({"_id": {"$ne": first_company["_id"]}})
            
    except Exception as e:
            
        logger.warning(f"Index creation issue: {e}")
            
    # Create password_reset_tokens collection if it doesn't exist
    try:
        if "password_reset_tokens" not in existing_collections:
            await database.create_collection("password_reset_tokens")        
        # Index 1: Compound index on (email, role, is_used) - Fast OTP lookup
        await database["password_reset_tokens"].create_index(
            [("email", 1), ("role", 1), ("is_used", 1)],
            name="reset_token_lookup_idx"
        )        
        # Index 2: TTL index on expires_at - Auto-delete expired tokens after 24 hours
        await database["password_reset_tokens"].create_index(
            "expires_at",
            name="reset_token_expires_idx",
            expireAfterSeconds=86400  # 24 hours
        )        
    except Exception as e:        
        logger.warning(f"Index creation issue: {e}")        
    # Create cme_registrations collection if it doesn't exist
    try:
        if "cme_registrations" not in existing_collections:
            await database.create_collection("cme_registrations")        
        # Index 1: Compound unique index on (cme_id, doctor_id) - Prevent duplicate registrations
        await database["cme_registrations"].create_index(
            [("cme_id", 1), ("doctor_id", 1)],
            unique=True,
            name="registration_unique_idx"
        )        
        # Index 2: Index on cme_id - Fast retrieval of all registrations for an event
        await database["cme_registrations"].create_index(
            "cme_id",
            name="registration_cme_idx"
        )        
        # Index 3: Index on doctor_id - Fast retrieval of doctor's registrations
        await database["cme_registrations"].create_index(
            "doctor_id",
            name="registration_doctor_idx"
        )        
        # Index 4: Compound index on (cme_id, registration_status) - Fast filtering
        await database["cme_registrations"].create_index(
            [("cme_id", 1), ("registration_status", 1)],
            name="registration_cme_status_idx"
        )        
    except Exception as e:        
        logger.warning(f"Index creation issue: {e}")        
    # Create communications collection if it doesn't exist
    try:
        if "communications" not in existing_collections:
            await database.create_collection("communications")        
        # Index 1: Compound index on (is_active, expires_at) - Fast active communications query
        await database["communications"].create_index(
            [("is_active", 1), ("expires_at", 1)],
            name="comm_active_expires_idx"
        )        
        # Index 2: Index on targeting.zones - Fast zone-based targeting
        await database["communications"].create_index(
            "targeting.zones",
            name="comm_zones_idx"
        )        
        # Index 3: Index on targeting.states - Fast state-based targeting
        await database["communications"].create_index(
            "targeting.states",
            name="comm_states_idx"
        )        
        # Index 4: Index on targeting.territories - Fast territory-based targeting
        await database["communications"].create_index(
            "targeting.territories",
            name="comm_territories_idx"
        )        
        # Index 5: Index on targeting.specific_mrs - Fast specific MR targeting
        await database["communications"].create_index(
            "targeting.specific_mrs",
            name="comm_specific_mrs_idx"
        )        
        # Index 6: Index on created_at - Fast sorting by date
        await database["communications"].create_index(
            "created_at",
            name="comm_created_at_idx"
        )        
        # Index 7: Index on priority - Fast filtering by priority
        await database["communications"].create_index(
            "priority",
            name="comm_priority_idx"
        )        
    except Exception as e:        
        logger.warning(f"Index creation issue: {e}")        
    # Create communication_reads collection if it doesn't exist
    try:
        if "communication_reads" not in existing_collections:
            await database.create_collection("communication_reads")        
        # Index 1: Compound unique index on (communication_id, mr_id) - Prevent duplicate reads
        await database["communication_reads"].create_index(
            [("communication_id", 1), ("mr_id", 1)],
            unique=True,
            name="comm_read_unique_idx"
        )        
        # Index 2: Index on communication_id - Fast analytics queries
        await database["communication_reads"].create_index(
            "communication_id",
            name="comm_read_comm_idx"
        )        
        # Index 3: Index on mr_id - Fast MR read history
        await database["communication_reads"].create_index(
            "mr_id",
            name="comm_read_mr_idx"
        )        
        # Index 4: Index on read_at - Fast sorting by read time
        await database["communication_reads"].create_index(
            "read_at",
            name="comm_read_at_idx"
        )        
        # Index 5: TTL index on created_at - Auto-delete old read records after 90 days
        await database["communication_reads"].create_index(
            "created_at",
            name="comm_read_ttl_idx",
            expireAfterSeconds=7776000  # 90 days
        )        
    except Exception as e:        
        logger.warning(f"Index creation issue: {e}")        
    # Create departments collection if it doesn't exist
    try:
        if "departments" not in existing_collections:
            await database.create_collection("departments")        
        # Index 1: Unique index on code - Prevent duplicate department codes
        await database["departments"].create_index(
            "code",
            unique=True,
            name="dept_code_unique_idx"
        )        
        # Index 2: Index on is_active - Fast active departments query
        await database["departments"].create_index(
            "is_active",
            name="dept_active_idx"
        )        
        # Index 3: Index on order - Fast sorting
        await database["departments"].create_index(
            "order",
            name="dept_order_idx"
        )        
        # Seed initial departments if collection is empty
        dept_count = await database["departments"].count_documents({})
        if dept_count == 0:
            from datetime import datetime
            initial_departments = [
                {
                    "code": "hr",
                    "name": "Human Resources",
                    "description": "Leave, transfers, performance issues, harassment complaints",
                    "is_active": True,
                    "order": 1,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                {
                    "code": "finance",
                    "name": "Finance & Accounts",
                    "description": "Salary, reimbursements, incentives, travel claims",
                    "is_active": True,
                    "order": 2,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                {
                    "code": "it",
                    "name": "IT Support",
                    "description": "System access, technical issues, software problems",
                    "is_active": True,
                    "order": 3,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            ]
            await database["departments"].insert_many(initial_departments)
        
    except Exception as e:
        
        logger.warning(f"Index creation issue: {e}")
        
    # Create grievances collection if it doesn't exist
    try:
        if "grievances" not in existing_collections:
            await database.create_collection("grievances")        
        # Index 1: Unique index on ticket_id - Prevent duplicate tickets
        await database["grievances"].create_index(
            "ticket_id",
            unique=True,
            name="grievance_ticket_unique_idx"
        )        
        # Index 2: Compound index on (created_by, status) - Fast MR grievance queries
        await database["grievances"].create_index(
            [("created_by", 1), ("status", 1)],
            name="grievance_mr_status_idx"
        )        
        # Index 3: Compound index on (department, status) - Fast admin queries
        await database["grievances"].create_index(
            [("department", 1), ("status", 1)],
            name="grievance_dept_status_idx"
        )        
        # Index 4: Compound index on (status, priority) - Fast sorting
        await database["grievances"].create_index(
            [("status", 1), ("priority", -1)],
            name="grievance_status_priority_idx"
        )        
        # Index 5: Index on created_at - Fast date sorting
        await database["grievances"].create_index(
            [("created_at", -1)],
            name="grievance_created_at_idx"
        )        
        # Index 6: Index on is_active - Fast active grievances query
        await database["grievances"].create_index(
            "is_active",
            name="grievance_active_idx"
        )        
        # Index 7: Index on created_by - Fast MR lookup
        await database["grievances"].create_index(
            "created_by",
            name="grievance_created_by_idx"
        )        
        # Index 8: Index on department - Fast department lookup
        await database["grievances"].create_index(
            "department",
            name="grievance_department_idx"
        )        
    except Exception as e:        
        logger.warning(f"Index creation issue: {e}")        
    # ========================================================================
    # SFE (Sales Force Effectiveness) Collections
    # ========================================================================
    
    # Create doctor_assignments collection
    try:
        # Index 1: Compound unique index on (mr_id, doctor_id) - Prevent duplicate assignments
        await database["doctor_assignments"].create_index(
            [("mr_id", 1), ("doctor_id", 1)],
            unique=True,
            name="assignment_mr_doctor_idx"
        )        
        # Index 2: Index on mr_id - Fast MR assignments lookup
        await database["doctor_assignments"].create_index(
            "mr_id",
            name="assignment_mr_idx"
        )        
        # Index 3: Index on doctor_id - Fast doctor assignment lookup
        await database["doctor_assignments"].create_index(
            "doctor_id",
            name="assignment_doctor_idx"
        )        
        # Index 4: Index on classification - Fast filtering by class
        await database["doctor_assignments"].create_index(
            "classification",
            name="assignment_class_idx"
        )
    except Exception as e:
        logger.warning(f"Index creation issue: {e}")
    
    # Create sfe_settings collection (single document, no indexes needed)
    if "sfe_settings" not in existing_collections:
        await database.create_collection("sfe_settings")
    
    # Create prescription_commitments collection
    try:
        # Index 1: Index on mr_id - Fast MR commitments lookup
        await database["prescription_commitments"].create_index(
            "mr_id",
            name="commitment_mr_idx"
        )        
        # Index 2: Index on doctor_id - Fast doctor commitments lookup
        await database["prescription_commitments"].create_index(
            "doctor_id",
            name="commitment_doctor_idx"
        )        
        # Index 3: Index on product_id - Fast product commitments lookup
        await database["prescription_commitments"].create_index(
            "product_id",
            name="commitment_product_idx"
        )        
        # Index 4: Index on territory - Fast territory-wise aggregation
        await database["prescription_commitments"].create_index(
            "territory",
            name="commitment_territory_idx"
        )        
        # Index 5: Index on status - Fast active commitments filtering
        await database["prescription_commitments"].create_index(
            "status",
            name="commitment_status_idx"
        )        
        # Index 6: Index on created_at - Fast sorting by date
        await database["prescription_commitments"].create_index(
            "created_at",
            name="commitment_created_idx"
        )
    except Exception as e:
        logger.warning(f"Index creation issue: {e}")
    
    # Create chemist_checks collection (optional)
    try:
        # Index 1: Index on mr_id - Fast MR checks lookup
        await database["chemist_checks"].create_index(
            "mr_id",
            name="chemist_mr_idx"
        )        
        # Index 2: Index on product_id - Fast product checks lookup
        await database["chemist_checks"].create_index(
            "product_id",
            name="chemist_product_idx"
        )        
        # Index 3: Index on territory - Fast territory-wise aggregation
        await database["chemist_checks"].create_index(
            "territory",
            name="chemist_territory_idx"
        )        
        # Index 4: Index on date - Fast date-based queries
        await database["chemist_checks"].create_index(
            "date",
            name="chemist_date_idx"
        )
    except Exception as e:
        logger.warning(f"Index creation issue: {e}")
    
    # Create doctor_requests collection (MR request → Admin approval workflow)
    try:
        # Index 1: Index on status - Fast pending requests filtering
        await database["doctor_requests"].create_index(
            "status",
            name="doctor_request_status_idx"
        )        
        # Index 2: Index on requested_by - Fast MR requests lookup
        await database["doctor_requests"].create_index(
            "requested_by",
            name="doctor_request_mr_idx"
        )        
        # Index 3: Index on created_at - Fast sorting by date
        await database["doctor_requests"].create_index(
            [("created_at", -1)],
            name="doctor_request_created_idx"
        )        
        # Index 4: Compound index on email + status - Fast duplicate check
        await database["doctor_requests"].create_index(
            [("email", 1), ("status", 1)],
            name="doctor_request_email_status_idx"
        )
    except Exception as e:
        logger.warning(f"Index creation issue: {e}")
    
    logger.info("Collections and indexes initialized successfully")


