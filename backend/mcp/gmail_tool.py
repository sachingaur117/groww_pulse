"""
gmail_tool.py — Phase 5: Gmail Export

Creates a draft email containing the Weekly Product Pulse and Fee Explainer.
Uses a Service Account or OAuth credentials (token_gmail.json).
"""

import base64
import os
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json

# Scope for modifying Gmail drafts
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
TOKEN_PATH = Path(__file__).resolve().parents[2] / "token_gmail.json"
CREDENTIALS_PATH = Path(__file__).resolve().parents[2] / "credentials.json"


def get_gmail_service():
    """Initializes and returns the Gmail v1 service."""
    creds = None
    
    # 1. Try Service Account (Primary for Production/Render)
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        try:
            info = json.loads(service_account_json)
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            # Service accounts need to specify who they are acting as for Gmail
            # unless Domain-Wide Delegation is used. 
            # For simplicity, we assume the credentials.json provided HAS the necessary permissions.
            return build("gmail", "v1", credentials=creds)
        except Exception as e:
            print(f"Warning: Failed to load Service Account credentials from env: {e}")

    # 2. Try Local Token (OAuth Fallback)
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    
    # 3. Handle Flow (Local Development Only)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError("Google OAuth credentials.json missing and no GOOGLE_SERVICE_ACCOUNT_JSON env var found. Cannot authenticate.")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=8080)
        
        # Save token for next time (local dev)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def create_draft(recipient: str, subject: str, body: str) -> dict:
    """Creates a draft email in the authenticated user's Gmail account."""
    try:
        service = get_gmail_service()
        
        # Build the email
        message = EmailMessage()
        message.set_content(body)
        message["To"] = recipient
        message["From"] = "me"
        message["Subject"] = subject
        
        # Encode for the API
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"message": {"raw": encoded_message}}
        
        # Call the Gmail API
        draft = service.users().drafts().create(userId="me", body=create_message).execute()
        
        return {"status": "success", "draft_id": draft["id"]}
        
    except HttpError as error:
        raise Exception(f"Gmail API Error: {error}")
    except Exception as e:
        raise Exception(f"Failed to create draft: {str(e)}")
