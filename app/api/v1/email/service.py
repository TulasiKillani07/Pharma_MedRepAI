"""
Email Service for sending invitation and notification emails.
Uses Gmail SMTP with async support.
"""

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str = None
) -> bool:
    """
    Send an email using Gmail SMTP.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML email body
        text_content: Plain text fallback (optional)
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    # Check if email is configured
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD or not settings.SMTP_FROM_EMAIL:
        logger.warning("Email not configured. Skipping email send. Please configure SMTP settings in .env file.")
        return False
    
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        message["To"] = to_email
        message["Subject"] = subject
        
        # Add plain text version (fallback)
        if text_content:
            part1 = MIMEText(text_content, "plain")
            message.attach(part1)
        
        # Add HTML version
        part2 = MIMEText(html_content, "html")
        message.attach(part2)
        
        # Send email via Gmail SMTP
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True
        )
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False


async def send_invitation_email(
    to_email: str,
    name: str,
    role: str,
    email: str,
    password: str
) -> bool:
    """
    Send invitation email to newly created doctor or MR.
    
    Args:
        to_email: Recipient email address
        name: User's full name
        role: "doctor" or "mr"
        email: Login email
        password: Temporary password
        
    Returns:
        bool: True if sent successfully
    """
    login_url = f"{settings.FRONTEND_URL}/login"
    role_title = "Doctor" if role == "doctor" else "Medical Representative"
    greeting = f"Dr. {name}" if role == "doctor" else name
    
    subject = f"Welcome to {settings.SMTP_FROM_NAME} - Your Account is Ready!"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f9f9f9;
            }}
            .header {{
                background-color: #007bff;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: white;
                padding: 30px;
                border-radius: 0 0 5px 5px;
            }}
            .credentials {{
                background-color: #f5f5f5;
                padding: 20px;
                margin: 20px 0;
                border-left: 4px solid #007bff;
            }}
            .credentials p {{
                margin: 10px 0;
            }}
            .button {{
                display: inline-block;
                background-color: #007bff;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .warning {{
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                color: #666;
                font-size: 12px;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to {settings.SMTP_FROM_NAME}!</h1>
            </div>
            <div class="content">
                <p>Dear {greeting},</p>
                
                <p>Your <strong>{role_title}</strong> account has been successfully created by the administrator.</p>
                
                <p>You can now access the platform and start using all the features available to you.</p>
                
                <div class="credentials">
                    <h3 style="margin-top: 0;">Your Login Credentials:</h3>
                    <p><strong>Email:</strong> {email}</p>
                    <p><strong>Temporary Password:</strong> <code style="background: #e9ecef; padding: 2px 6px; border-radius: 3px;">{password}</code></p>
                </div>
                
                <div style="text-align: center;">
                    <a href="{login_url}" class="button">Login to Your Account</a>
                </div>
                
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong>
                    <p style="margin: 5px 0 0 0;">For your security, please change your password immediately after your first login.</p>
                </div>
                
                <p>If you have any questions or need assistance, please contact your administrator.</p>
                
                <p>Best regards,<br>
                <strong>{settings.SMTP_FROM_NAME} Team</strong></p>
            </div>
            <div class="footer">
                <p>This is an automated email. Please do not reply to this message.</p>
                <p>&copy; 2024 {settings.SMTP_FROM_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Welcome to {settings.SMTP_FROM_NAME}!
    
    Dear {greeting},
    
    Your {role_title} account has been successfully created.
    
    Login Credentials:
    Email: {email}
    Temporary Password: {password}
    
    Login URL: {login_url}
    
    IMPORTANT: Please change your password immediately after your first login.
    
    Best regards,
    {settings.SMTP_FROM_NAME} Team
    """
    
    return await send_email(to_email, subject, html_content, text_content)


async def send_bulk_upload_summary_email(
    admin_email: str,
    admin_name: str,
    role: str,
    total_created: int,
    successful_emails: int,
    failed_emails: int,
    created_users: List[Dict[str, str]]
) -> bool:
    """
    Send summary email to admin after bulk upload.
    
    Args:
        admin_email: Admin's email address
        admin_name: Admin's name
        role: "doctor" or "mr"
        total_created: Total users created
        successful_emails: Number of emails sent successfully
        failed_emails: Number of emails that failed
        created_users: List of created users with name and email
        
    Returns:
        bool: True if sent successfully
    """
    role_title = "Doctors" if role == "doctor" else "Medical Representatives"
    
    subject = f"Bulk Upload Summary - {total_created} {role_title} Created"
    
    # Build user list HTML
    user_list_html = ""
    for user in created_users:
        status = "✅ Email sent" if user.get("email_sent") else "❌ Email failed"
        user_list_html += f"<tr><td>{user['name']}</td><td>{user['email']}</td><td>{status}</td></tr>"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 700px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #28a745;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: white;
                padding: 30px;
                border: 1px solid #ddd;
                border-radius: 0 0 5px 5px;
            }}
            .stats {{
                display: flex;
                justify-content: space-around;
                margin: 20px 0;
            }}
            .stat-box {{
                text-align: center;
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 5px;
                flex: 1;
                margin: 0 10px;
            }}
            .stat-number {{
                font-size: 32px;
                font-weight: bold;
                color: #007bff;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background-color: #f8f9fa;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Bulk Upload Completed</h1>
            </div>
            <div class="content">
                <p>Dear {admin_name},</p>
                
                <p>Your bulk upload of <strong>{role_title}</strong> has been completed successfully.</p>
                
                <div class="stats">
                    <div class="stat-box">
                        <div class="stat-number">{total_created}</div>
                        <div>Users Created</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number" style="color: #28a745;">{successful_emails}</div>
                        <div>Emails Sent</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number" style="color: #dc3545;">{failed_emails}</div>
                        <div>Emails Failed</div>
                    </div>
                </div>
                
                <h3>Created Users:</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Email</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {user_list_html}
                    </tbody>
                </table>
                
                <p>All users have been notified via email with their login credentials.</p>
                
                <p>Best regards,<br>
                <strong>{settings.SMTP_FROM_NAME} System</strong></p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return await send_email(admin_email, subject, html_content)



async def send_password_reset_otp_email(
    to_email: str,
    name: str,
    otp: str
) -> bool:
    """
    Send password reset OTP email.
    
    Args:
        to_email: Recipient email address
        name: User's name
        otp: 6-digit OTP code
        
    Returns:
        bool: True if sent successfully
    """
    subject = f"Password Reset OTP - {settings.SMTP_FROM_NAME}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f9f9f9;
            }}
            .header {{
                background-color: #dc3545;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: white;
                padding: 30px;
                border-radius: 0 0 5px 5px;
            }}
            .otp-box {{
                background-color: #f5f5f5;
                padding: 30px;
                margin: 30px 0;
                text-align: center;
                border-left: 4px solid #dc3545;
                border-radius: 5px;
            }}
            .otp-code {{
                font-size: 48px;
                font-weight: bold;
                color: #dc3545;
                letter-spacing: 8px;
                margin: 20px 0;
                font-family: 'Courier New', monospace;
            }}
            .warning {{
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                color: #666;
                font-size: 12px;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Password Reset Request</h1>
            </div>
            <div class="content">
                <p>Dear {name},</p>
                
                <p>We received a request to reset your password. Use the OTP code below to reset your password:</p>
                
                <div class="otp-box">
                    <h2 style="margin-top: 0; color: #666;">Your OTP Code:</h2>
                    <div class="otp-code">{otp}</div>
                    <p style="color: #666; margin-bottom: 0;">This code will expire in <strong>15 minutes</strong></p>
                </div>
                
                <p>Enter this code on the password reset page to continue.</p>
                
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong>
                    <p style="margin: 5px 0 0 0;">If you didn't request this password reset, please ignore this email or contact your administrator immediately. Your account is still secure.</p>
                </div>
                
                <p>Best regards,<br>
                <strong>{settings.SMTP_FROM_NAME} Team</strong></p>
            </div>
            <div class="footer">
                <p>This is an automated email. Please do not reply to this message.</p>
                <p>&copy; 2024 {settings.SMTP_FROM_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Password Reset Request
    
    Dear {name},
    
    We received a request to reset your password.
    
    Your OTP Code: {otp}
    
    This code will expire in 15 minutes.
    
    If you didn't request this password reset, please ignore this email.
    
    Best regards,
    {settings.SMTP_FROM_NAME} Team
    """
    
    return await send_email(to_email, subject, html_content, text_content)


async def send_password_reset_confirmation_email(
    to_email: str,
    name: str,
    timestamp: str,
    ip_address: str = "Unknown"
) -> bool:
    """
    Send password reset confirmation email.
    
    Args:
        to_email: Recipient email address
        name: User's name
        timestamp: When password was changed
        ip_address: IP address of the request
        
    Returns:
        bool: True if sent successfully
    """
    subject = f"Password Changed Successfully - {settings.SMTP_FROM_NAME}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f9f9f9;
            }}
            .header {{
                background-color: #28a745;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: white;
                padding: 30px;
                border-radius: 0 0 5px 5px;
            }}
            .info-box {{
                background-color: #f5f5f5;
                padding: 20px;
                margin: 20px 0;
                border-left: 4px solid #28a745;
                border-radius: 5px;
            }}
            .warning {{
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                color: #666;
                font-size: 12px;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Password Changed Successfully</h1>
            </div>
            <div class="content">
                <p>Dear {name},</p>
                
                <p>Your password has been successfully changed.</p>
                
                <div class="info-box">
                    <p style="margin: 5px 0;"><strong>Changed at:</strong> {timestamp}</p>
                    <p style="margin: 5px 0;"><strong>IP Address:</strong> {ip_address}</p>
                </div>
                
                <p>You can now login with your new password.</p>
                
                <div class="warning">
                    <strong>⚠️ Didn't make this change?</strong>
                    <p style="margin: 5px 0 0 0;">If you didn't change your password, please contact your administrator immediately. Your account may be compromised.</p>
                </div>
                
                <p>Best regards,<br>
                <strong>{settings.SMTP_FROM_NAME} Team</strong></p>
            </div>
            <div class="footer">
                <p>This is an automated email. Please do not reply to this message.</p>
                <p>&copy; 2024 {settings.SMTP_FROM_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Password Changed Successfully
    
    Dear {name},
    
    Your password has been successfully changed.
    
    Changed at: {timestamp}
    IP Address: {ip_address}
    
    If you didn't make this change, please contact your administrator immediately.
    
    Best regards,
    {settings.SMTP_FROM_NAME} Team
    """
    
    return await send_email(to_email, subject, html_content, text_content)



async def send_cme_registration_confirmation_email(
    to_email: str,
    doctor_name: str,
    event_title: str,
    event_date: str,
    event_time: str,
    event_type: str,
    event_mode: str,
    speaker: str,
    meeting_link: str = None,
    platform: str = None,
    venue_name: str = None,
    address: str = None,
    registration_passcode: str = None
) -> bool:
    """
    Send CME registration confirmation email.
    
    Args:
        to_email: Doctor's email address
        doctor_name: Doctor's name
        event_title: CME event title
        event_date: Event date (formatted string)
        event_time: Event time (e.g., "10:00 AM - 12:00 PM")
        event_type: Event type (Webinar, Conference, etc.)
        event_mode: "online" or "offline"
        speaker: Speaker name
        meeting_link: Meeting URL (for online events)
        platform: Platform name (for online events)
        venue_name: Venue name (for offline events)
        address: Venue address (for offline events)
        registration_passcode: Passcode for offline event registration
        
    Returns:
        bool: True if sent successfully
    """
    subject = f"Registration Confirmed: {event_title}"
    
    # Generate event mode specific content
    if event_mode == "online":
        event_details = f"""
        <div style="background: #e0f2fe; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #0369a1; margin-top: 0;">📍 Online Event Details</h3>
            <p style="margin: 8px 0;"><strong>Platform:</strong> {platform or 'Online'}</p>
            <p style="margin: 8px 0;"><strong>Meeting Link:</strong><br>
            <a href="{meeting_link}" style="color: #0369a1; word-break: break-all; font-size: 14px;">{meeting_link}</a></p>
            <div style="background: #bae6fd; padding: 15px; border-radius: 6px; margin-top: 15px;">
                <p style="color: #075985; font-size: 14px; margin: 0;">
                    💡 <strong>Note:</strong> The "Join Meeting" button will appear 2 minutes before the event starts in your dashboard.
                </p>
            </div>
        </div>
        """
    else:  # offline
        passcode_html = ""
        if registration_passcode:
            passcode_html = f"""
            <div style="background: #fef3c7; padding: 15px; border-radius: 6px; margin-top: 15px; text-align: center;">
                <p style="margin: 0 0 10px 0; color: #92400e;"><strong>📋 Registration Passcode:</strong></p>
                <div style="background: #fbbf24; padding: 10px 20px; border-radius: 6px; display: inline-block;">
                    <span style="font-size: 24px; font-weight: bold; color: #78350f; letter-spacing: 2px;">{registration_passcode}</span>
                </div>
                <p style="margin: 10px 0 0 0; font-size: 13px; color: #92400e;">Please show this passcode at the registration desk</p>
            </div>
            """
        
        event_details = f"""
        <div style="background: #fef3c7; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #92400e; margin-top: 0;">📍 Venue Details</h3>
            <p style="margin: 8px 0;"><strong>Venue:</strong> {venue_name}</p>
            <p style="margin: 8px 0;"><strong>Address:</strong><br>{address}</p>
            {passcode_html}
            <div style="background: #fde68a; padding: 15px; border-radius: 6px; margin-top: 15px;">
                <p style="color: #92400e; font-size: 14px; margin: 0;">
                    💡 <strong>Note:</strong> Please arrive 15 minutes early for registration.
                </p>
            </div>
        </div>
        """
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f9f9f9;
            }}
            .header {{
                background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                color: white;
                padding: 30px 20px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }}
            .success-icon {{
                font-size: 48px;
                margin-bottom: 10px;
            }}
            .content {{
                background-color: white;
                padding: 30px;
                border-radius: 0 0 10px 10px;
            }}
            .event-info {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
                border-left: 4px solid #3b82f6;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .event-info h2 {{
                color: #1e40af;
                margin-top: 0;
                font-size: 22px;
            }}
            .event-info p {{
                margin: 10px 0;
                font-size: 15px;
            }}
            .footer {{
                text-align: center;
                margin-top: 20px;
                color: #666;
                font-size: 12px;
                padding: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="success-icon">🎉</div>
                <h1 style="margin: 0; font-size: 28px;">Registration Confirmed!</h1>
            </div>
            <div class="content">
                <p>Dear Dr. {doctor_name},</p>
                <p>You have successfully registered for the following CME event:</p>
                
                <div class="event-info">
                    <h2>{event_title}</h2>
                    <p><strong>📅 Date:</strong> {event_date}</p>
                    <p><strong>🕐 Time:</strong> {event_time}</p>
                    <p><strong>📚 Type:</strong> {event_type}</p>
                    <p><strong>🎤 Speaker:</strong> {speaker}</p>
                    <p><strong>🌐 Mode:</strong> <span style="text-transform: uppercase; background: #dbeafe; padding: 3px 8px; border-radius: 4px; font-size: 13px;">{event_mode}</span></p>
                </div>
                
                {event_details}
                
                <p style="margin-top: 30px; font-size: 15px;">We look forward to seeing you at the event!</p>
                
                <p style="margin-top: 20px;">Best regards,<br>
                <strong>{settings.SMTP_FROM_NAME} Team</strong></p>
            </div>
            <div class="footer">
                <p>This is an automated confirmation email. Please do not reply.</p>
                <p>&copy; 2024 {settings.SMTP_FROM_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Registration Confirmed: {event_title}
    
    Dear Dr. {doctor_name},
    
    You have successfully registered for the following CME event:
    
    Event: {event_title}
    Date: {event_date}
    Time: {event_time}
    Type: {event_type}
    Speaker: {speaker}
    Mode: {event_mode.upper()}
    
    {"Meeting Link: " + meeting_link if meeting_link else ""}
    {"Venue: " + venue_name if venue_name else ""}
    {"Address: " + address if address else ""}
    {"Registration Passcode: " + registration_passcode if registration_passcode else ""}
    
    We look forward to seeing you at the event!
    
    Best regards,
    {settings.SMTP_FROM_NAME} Team
    """
    
    return await send_email(to_email, subject, html_content, text_content)
