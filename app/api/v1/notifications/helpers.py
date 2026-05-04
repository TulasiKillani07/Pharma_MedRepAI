"""
Notification Helper Functions

Pre-built functions for common notification scenarios.
Makes it easy to send notifications with just one line of code.
"""

from typing import List, Dict, Any
from app.api.v1.notifications.service import create_notification, create_bulk_notifications
from app.models.notification_model import NotificationType


# ============================================================================
# CONNECTION NOTIFICATIONS
# ============================================================================

async def notify_connection_request(receiver_id: str, requester_name: str, requester_id: str, requester_role: str, connection_id: str):
    """Notify when someone sends a connection request"""
    await create_notification(
        user_id=receiver_id,
        notification_type=NotificationType.CONNECTION_REQUEST,
        title="New Connection Request",
        message=f"{requester_name} wants to connect with you",
        data={
            "connection_id": connection_id,
            "requester_id": requester_id,
            "requester_name": requester_name,
            "requester_role": requester_role
        }
    )


async def notify_connection_accepted(requester_id: str, accepter_name: str, accepter_id: str, accepter_role: str, connection_id: str):
    """Notify when someone accepts your connection request"""
    await create_notification(
        user_id=requester_id,
        notification_type=NotificationType.CONNECTION_ACCEPTED,
        title="Connection Accepted",
        message=f"{accepter_name} accepted your connection request",
        data={
            "connection_id": connection_id,
            "accepter_id": accepter_id,
            "accepter_name": accepter_name,
            "accepter_role": accepter_role
        }
    )


# ============================================================================
# POST/FEED NOTIFICATIONS
# ============================================================================

async def notify_post_liked(post_id: str, post_author_id: str, liker_name: str, liker_id: str):
    """Notify when someone likes your post"""
    await create_notification(
        user_id=post_author_id,
        notification_type=NotificationType.POST_LIKED,
        title="Post Liked",
        message=f"{liker_name} liked your post",
        data={
            "post_id": post_id,
            "liker_id": liker_id,
            "liker_name": liker_name
        }
    )


async def notify_post_commented(post_id: str, post_author_id: str, commenter_name: str, commenter_id: str, comment_id: str):
    """Notify when someone comments on your post"""
    await create_notification(
        user_id=post_author_id,
        notification_type=NotificationType.POST_COMMENTED,
        title="New Comment",
        message=f"{commenter_name} commented on your post",
        data={
            "post_id": post_id,
            "comment_id": comment_id,
            "commenter_id": commenter_id,
            "commenter_name": commenter_name
        }
    )


async def notify_post_shared(receiver_id: str, post_id: str, sharer_name: str, sharer_id: str, personal_message: str = None):
    """Notify when someone shares a post with you"""
    message = f"{sharer_name} shared a post with you"
    if personal_message:
        message += f': "{personal_message}"'
    
    await create_notification(
        user_id=receiver_id,
        notification_type=NotificationType.POST_SHARED,
        title="Post Shared",
        message=message,
        data={
            "post_id": post_id,
            "sharer_id": sharer_id,
            "sharer_name": sharer_name,
            "personal_message": personal_message
        }
    )


# ============================================================================
# CHAT NOTIFICATIONS
# ============================================================================

async def notify_new_message(receiver_id: str, sender_name: str, sender_id: str, conversation_id: str, message_preview: str):
    """Notify when you receive a new direct message"""
    # Truncate preview to 50 characters
    if len(message_preview) > 50:
        message_preview = message_preview[:50] + "..."
    
    await create_notification(
        user_id=receiver_id,
        notification_type=NotificationType.NEW_MESSAGE,
        title="New Message",
        message=f"{sender_name}: {message_preview}",
        data={
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "message_preview": message_preview
        }
    )


# ============================================================================
# GROUP NOTIFICATIONS
# ============================================================================

async def notify_group_message(group_id: str, group_name: str, sender_name: str, sender_id: str, message_preview: str, member_ids: List[str], exclude_sender: bool = True):
    """Notify group members about a new message"""
    # Truncate preview to 50 characters
    if len(message_preview) > 50:
        message_preview = message_preview[:50] + "..."
    
    # Exclude sender from notifications
    if exclude_sender and sender_id in member_ids:
        member_ids = [mid for mid in member_ids if mid != sender_id]
    
    if member_ids:
        await create_bulk_notifications(
            user_ids=member_ids,
            notification_type=NotificationType.GROUP_MESSAGE,
            title=f"{group_name}",
            message=f"{sender_name}: {message_preview}",
            data={
                "group_id": group_id,
                "group_name": group_name,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "message_preview": message_preview
            }
        )


async def notify_group_added(user_id: str, group_id: str, group_name: str, added_by_name: str, added_by_id: str):
    """Notify when you're added to a group"""
    await create_notification(
        user_id=user_id,
        notification_type=NotificationType.GROUP_ADDED,
        title="Added to Group",
        message=f"{added_by_name} added you to {group_name}",
        data={
            "group_id": group_id,
            "group_name": group_name,
            "added_by_id": added_by_id,
            "added_by_name": added_by_name
        }
    )


# ============================================================================
# CME NOTIFICATIONS
# ============================================================================

async def notify_cme_created(cme_id: str, cme_title: str, event_date: str, event_time: str, doctor_ids: List[str]):
    """Notify all doctors about a new CME event"""
    if doctor_ids:
        await create_bulk_notifications(
            user_ids=doctor_ids,
            notification_type=NotificationType.CME_CREATED,
            title="New CME Event",
            message=f"New event: {cme_title} on {event_date}",
            data={
                "cme_id": cme_id,
                "cme_title": cme_title,
                "event_date": event_date,
                "event_time": event_time
            }
        )


async def notify_cme_updated(cme_id: str, cme_title: str, event_date: str, event_time: str, doctor_ids: List[str], updated_fields: List[str]):
    """Notify all doctors when CME event is updated"""
    if doctor_ids:
        fields_text = ", ".join(updated_fields[:3])  # Show first 3 fields
        if len(updated_fields) > 3:
            fields_text += f" and {len(updated_fields) - 3} more"
        
        await create_bulk_notifications(
            user_ids=doctor_ids,
            notification_type=NotificationType.CME_UPDATED,
            title="CME Event Updated",
            message=f"{cme_title} has been updated ({fields_text})",
            data={
                "cme_id": cme_id,
                "cme_title": cme_title,
                "event_date": event_date,
                "event_time": event_time,
                "updated_fields": updated_fields
            }
        )


async def notify_cme_cancelled(cme_id: str, cme_title: str, event_date: str, doctor_ids: List[str], reason: str = None):
    """Notify all doctors when CME event is cancelled"""
    if doctor_ids:
        message = f"{cme_title} scheduled for {event_date} has been cancelled"
        if reason:
            message += f" - Reason: {reason}"
        
        await create_bulk_notifications(
            user_ids=doctor_ids,
            notification_type=NotificationType.CME_CANCELLED,
            title="CME Event Cancelled",
            message=message,
            data={
                "cme_id": cme_id,
                "cme_title": cme_title,
                "event_date": event_date,
                "reason": reason
            }
        )


async def notify_cme_reminder_1day(cme_id: str, cme_title: str, event_date: str, event_time: str, attendee_ids: List[str]):
    """Notify attendees 1 day before CME event"""
    if attendee_ids:
        await create_bulk_notifications(
            user_ids=attendee_ids,
            notification_type=NotificationType.CME_REMINDER_1DAY,
            title="Event Tomorrow",
            message=f"Reminder: {cme_title} tomorrow at {event_time}",
            data={
                "cme_id": cme_id,
                "cme_title": cme_title,
                "event_date": event_date,
                "event_time": event_time
            }
        )


async def notify_cme_reminder_1hour(cme_id: str, cme_title: str, event_time: str, meeting_link: str, attendee_ids: List[str]):
    """Notify attendees 1 hour before CME event"""
    if attendee_ids:
        await create_bulk_notifications(
            user_ids=attendee_ids,
            notification_type=NotificationType.CME_REMINDER_1HOUR,
            title="Event Starting Soon",
            message=f"{cme_title} starts in 1 hour",
            data={
                "cme_id": cme_id,
                "cme_title": cme_title,
                "event_time": event_time,
                "meeting_link": meeting_link
            }
        )


async def notify_cme_recording(cme_id: str, cme_title: str, recording_url: str, attendee_ids: List[str]):
    """Notify attendees when CME recording is available"""
    if attendee_ids:
        await create_bulk_notifications(
            user_ids=attendee_ids,
            notification_type=NotificationType.CME_RECORDING,
            title="Recording Available",
            message=f"Recording for {cme_title} is now available",
            data={
                "cme_id": cme_id,
                "cme_title": cme_title,
                "recording_url": recording_url
            }
        )


async def notify_cme_registration_confirmed(doctor_id: str, cme_id: str, cme_title: str, event_date: str, event_time: str):
    """Notify doctor when registration is confirmed"""
    await create_notification(
        user_id=doctor_id,
        notification_type=NotificationType.CME_REGISTRATION_CONFIRMED,
        title="Registration Confirmed",
        message=f"You're registered for {cme_title} on {event_date}",
        data={
            "cme_id": cme_id,
            "cme_title": cme_title,
            "event_date": event_date,
            "event_time": event_time
        }
    )


async def notify_cme_registration_cancelled_user(doctor_id: str, cme_id: str, cme_title: str, event_date: str):
    """Notify doctor when they cancel their registration"""
    await create_notification(
        user_id=doctor_id,
        notification_type=NotificationType.CME_REGISTRATION_CANCELLED,
        title="Registration Cancelled",
        message=f"Your registration for {cme_title} on {event_date} has been cancelled",
        data={
            "cme_id": cme_id,
            "cme_title": cme_title,
            "event_date": event_date
        }
    )


# ============================================================================
# DRUG NOTIFICATIONS
# ============================================================================

async def notify_drug_added(drug_id: str, drug_name: str, manufacturer: str, user_ids: List[str]):
    """Notify all doctors and MRs about a new drug"""
    if user_ids:
        await create_bulk_notifications(
            user_ids=user_ids,
            notification_type=NotificationType.DRUG_ADDED,
            title="New Drug Added",
            message=f"{drug_name} by {manufacturer} added to catalog",
            data={
                "drug_id": drug_id,
                "drug_name": drug_name,
                "manufacturer": manufacturer
            }
        )


# ============================================================================
# VISIT NOTIFICATIONS
# ============================================================================

async def notify_visit_scheduled(doctor_id: str, visit_id: str, mr_name: str, mr_id: str, scheduled_date: str, scheduled_time: str, purpose: str):
    """Notify doctor when MR schedules a visit"""
    await create_notification(
        user_id=doctor_id,
        notification_type=NotificationType.VISIT_SCHEDULED,
        title="Visit Scheduled",
        message=f"{mr_name} scheduled a visit on {scheduled_date} at {scheduled_time}",
        data={
            "visit_id": visit_id,
            "mr_id": mr_id,
            "mr_name": mr_name,
            "scheduled_date": scheduled_date,
            "scheduled_time": scheduled_time,
            "purpose": purpose
        }
    )


async def notify_visit_rescheduled(doctor_id: str, visit_id: str, mr_name: str, old_date: str, new_date: str, new_time: str, reason: str = None):
    """Notify doctor when visit is rescheduled"""
    message = f"{mr_name} rescheduled visit from {old_date} to {new_date} at {new_time}"
    if reason:
        message += f" - Reason: {reason}"
    
    await create_notification(
        user_id=doctor_id,
        notification_type=NotificationType.VISIT_RESCHEDULED,
        title="Visit Rescheduled",
        message=message,
        data={
            "visit_id": visit_id,
            "mr_name": mr_name,
            "old_date": old_date,
            "new_date": new_date,
            "new_time": new_time,
            "reason": reason
        }
    )


async def notify_visit_completed(mr_id: str, visit_id: str, doctor_name: str, doctor_id: str, completed_at: str):
    """Notify MR when visit is marked as completed"""
    await create_notification(
        user_id=mr_id,
        notification_type=NotificationType.VISIT_COMPLETED,
        title="Visit Completed",
        message=f"Visit with {doctor_name} marked as completed",
        data={
            "visit_id": visit_id,
            "doctor_id": doctor_id,
            "doctor_name": doctor_name,
            "completed_at": completed_at
        }
    )


async def notify_visit_cancelled(user_id: str, visit_id: str, cancelled_by_name: str, scheduled_date: str, cancel_reason: str = None):
    """Notify when visit is cancelled"""
    message = f"{cancelled_by_name} cancelled the visit scheduled for {scheduled_date}"
    if cancel_reason:
        message += f" - Reason: {cancel_reason}"
    
    await create_notification(
        user_id=user_id,
        notification_type=NotificationType.VISIT_CANCELLED,
        title="Visit Cancelled",
        message=message,
        data={
            "visit_id": visit_id,
            "cancelled_by_name": cancelled_by_name,
            "scheduled_date": scheduled_date,
            "cancel_reason": cancel_reason
        }
    )
