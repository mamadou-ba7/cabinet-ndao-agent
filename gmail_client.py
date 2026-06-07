import os
import base64
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
]

TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"


def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def get_unread_emails(service, max_results=10, label="INBOX"):
    result = service.users().messages().list(
        userId="me",
        labelIds=[label, "UNREAD"],
        maxResults=max_results,
    ).execute()
    messages = result.get("messages", [])
    emails = []
    for msg in messages:
        email_data = get_email_details(service, msg["id"])
        if email_data:
            emails.append(email_data)
    return emails


def get_email_details(service, msg_id):
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    body = _extract_body(msg["payload"])
    return {
        "id": msg_id,
        "thread_id": msg["threadId"],
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "subject": headers.get("Subject", "(Sans objet)"),
        "date": headers.get("Date", ""),
        "body": body,
        "snippet": msg.get("snippet", ""),
    }


def _extract_body(payload):
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                body += base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    elif payload["body"].get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
    return body.strip()


def create_draft(service, to, subject, body_text, thread_id=None):
    message = MIMEMultipart("alternative")
    message["to"] = to
    message["subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
    message.attach(MIMEText(body_text, "plain", "utf-8"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    draft_body = {"message": {"raw": raw}}
    if thread_id:
        draft_body["message"]["threadId"] = thread_id

    draft = service.users().drafts().create(userId="me", body=draft_body).execute()
    return draft["id"]


def send_email(service, to, subject, body_text, thread_id=None):
    message = MIMEMultipart("alternative")
    message["to"] = to
    message["subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
    message.attach(MIMEText(body_text, "plain", "utf-8"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    send_body = {"raw": raw}
    if thread_id:
        send_body["threadId"] = thread_id

    sent = service.users().messages().send(userId="me", body=send_body).execute()
    return sent["id"]


def mark_as_read(service, msg_id):
    service.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()


def add_label(service, msg_id, label_name):
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    label_id = next((l["id"] for l in labels if l["name"] == label_name), None)
    if not label_id:
        new_label = service.users().labels().create(
            userId="me", body={"name": label_name}
        ).execute()
        label_id = new_label["id"]
    service.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"addLabelIds": [label_id]},
    ).execute()
