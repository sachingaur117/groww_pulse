"""
gdocs_tool.py — Phase 5: Google Docs Export

Appends the generated Weekly Product Pulse narrative directly to a Google Doc.
Uses a Service Account or OAuth credentials (token.json).
"""

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scope for modifying Docs
SCOPES = ["https://www.googleapis.com/auth/documents"]
TOKEN_PATH = Path(__file__).resolve().parents[2] / "token_docs.json"
CREDENTIALS_PATH = Path(__file__).resolve().parents[2] / "credentials.json"

def get_docs_service():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError("Google OAuth credentials.json missing. Cannot authenticate.")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=8080)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("docs", "v1", credentials=creds)


def append_to_doc(doc_id: str, title: str, narrative: str) -> dict:
    """Appends text to the given Google Doc ID."""
    try:
        service = get_docs_service()
        
        # We'll append a title, followed by the narrative text
        text_to_append = f"\n\n================================\n{title}\n================================\n\n{narrative}\n"
        
        requests = [
            {
                "insertText": {
                    "endOfSegmentLocation": {},
                    "text": text_to_append
                }
            }
        ]
        
        result = service.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests}
        ).execute()

        return {"status": "success", "doc_id": doc_id, "updates": result.get("replies")}
        
    except HttpError as error:
        raise Exception(f"Google Docs API Error: {error}")
    except Exception as e:
         raise Exception(f"Failed to append to doc: {str(e)}")
