"""
gmail_tool.py — Phase 5: Gmail Export (Plan B: SMTP)

Creates and sends a draft email (or sends directly) using SMTP with an App Password.
This version replaces the Google API Client to avoid OAuth/Headless issues.
"""

import os
import smtplib
from email.message import EmailMessage

def create_draft(recipient: str, subject: str, body: str) -> dict:
    """Sends an email directly using Gmail SMTP and an App Password."""
    try:
        # Get credentials from environment
        gmail_user = os.environ.get("GMAIL_USER")
        gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
        
        if not gmail_user or not gmail_password:
            raise ValueError("GMAIL_USER or GMAIL_APP_PASSWORD not set in environment.")

        # Build the email
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = gmail_user
        msg["To"] = recipient

        # Connect to Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.send_message(msg)

        return {"status": "success", "message": f"Email sent successfully to {recipient}"}
        
    except Exception as e:
        raise Exception(f"Failed to send email via SMTP: {str(e)}")

# Keep this for backward compatibility if other parts of the app expect it
def get_gmail_service():
    """Dummy function for compatibility. SMTP version doesn't need a 'service' object."""
    return None
