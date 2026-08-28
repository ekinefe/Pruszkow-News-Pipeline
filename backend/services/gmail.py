import os
import base64
import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from backend.config import settings
from backend.services.database import database_service


class GmailService:
    def __init__(self):
        self._service = None
        self._creds = None

    def _token_path(self) -> Path:
        return Path(settings.token_file)

    def _credentials_path(self) -> Path:
        p = Path(settings.gmail_credentials_file)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / p
        return p

    def is_authenticated(self) -> bool:
        try:
            creds = Credentials.from_authorized_user_file(
                str(self._token_path()), settings.gmail_scopes
            )
            return creds.valid
        except Exception:
            return False

    def get_user_email(self) -> str | None:
        try:
            if not self.is_authenticated():
                return None
            service = self._get_service()
            profile = service.users().getProfile(userId="me").execute()
            return profile.get("emailAddress")
        except Exception:
            return None

    def authenticate(self, port: int = 0) -> dict:
        creds = None
        token_path = self._token_path()
        creds_path = self._credentials_path()

        if token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(token_path), settings.gmail_scopes
                )
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds or not creds.valid:
                if not creds_path.exists():
                    return {
                        "success": False,
                        "error": f"Credentials file not found: {creds_path}",
                    }
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(creds_path), settings.gmail_scopes
                )
                creds = flow.run_local_server(port=port)

            with open(token_path, "w") as token:
                token.write(creds.to_json())

        self._creds = creds
        self._service = build("gmail", "v1", credentials=creds)
        return {"success": True}

    def _get_service(self):
        if self._service:
            return self._service

        token_path = self._token_path()
        if not token_path.exists():
            raise RuntimeError("Not authenticated. Please authenticate first.")

        creds = Credentials.from_authorized_user_file(
            str(token_path), settings.gmail_scopes
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w") as token:
                token.write(creds.to_json())

        self._creds = creds
        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def fetch_emails(
        self,
        max_results: int = 10,
        query: str = "",
        mark_read: bool = False,
        add_label: bool = False,
    ) -> list[dict]:
        service = self._get_service()

        label_id = None
        if add_label:
            label_id = self._get_or_create_label(service, "listed")

        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        messages = results.get("messages", [])
        if not messages:
            return []

        emails = []
        for msg_meta in messages:
            msg_id = msg_meta["id"]
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
            payload = msg["payload"]
            headers = payload.get("headers", [])

            sender = next(
                (h["value"] for h in headers if h["name"].lower() == "from"),
                "Unknown Sender",
            )

            if database_service.is_sender_ignored(sender):
                continue

            title = next(
                (h["value"] for h in headers if h["name"].lower() == "subject"),
                "No Subject",
            )
            date = next(
                (h["value"] for h in headers if h["name"].lower() == "date"),
                "Unknown Date",
            )

            downloaded = self._download_attachments(service, msg_id, payload)

            email_data = {
                "id": msg_id,
                "sender": sender,
                "title": title,
                "date": date,
                "body": self._get_body(payload).strip(),
                "attachments": downloaded,
                "internalDate": int(msg.get("internalDate", 0)),
            }
            emails.append(email_data)

            modify_body = {}
            if mark_read:
                modify_body["removeLabelIds"] = ["UNREAD"]
            if add_label and label_id:
                modify_body["addLabelIds"] = [label_id]
            if modify_body:
                (
                    service.users()
                    .messages()
                    .modify(userId="me", id=msg_id, body=modify_body)
                    .execute()
                )

        emails.sort(key=lambda x: x["internalDate"], reverse=True)
        for e in emails:
            e.pop("internalDate", None)

        return emails

    def create_draft(
        self,
        headline: str,
        article_body: str,
        original_title: str,
        original_sender: str,
        seo_title: str = "",
        seo_description: str = "",
    ) -> str:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        service = self._get_service()
        profile = service.users().getProfile(userId="me").execute()
        user_email = profile["emailAddress"]

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Szkic] {headline}"
        msg["From"] = user_email
        msg["To"] = user_email

        seo_comment = ""
        if seo_title or seo_description:
            parts = []
            if seo_title:
                parts.append(f"SEO Title: {seo_title}")
            if seo_description:
                parts.append(f"SEO Description: {seo_description}")
            seo_comment = f"<!-- {' | '.join(parts)} -->\n\n"

        body = (
            f"Zrodlo: {original_sender}\n"
            f"Tytul oryginalny: {original_title}\n\n---\n\n"
            f"{seo_comment}{article_body}"
        )
        msg.attach(MIMEText(body, "plain", "utf-8"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        draft = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        return draft["id"]

    def _get_body(self, payload: dict) -> str:
        body = ""
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part["body"].get("data")
                    if data:
                        body += base64.urlsafe_b64decode(data).decode("utf-8")
                elif "parts" in part:
                    body += self._get_body(part)
        elif payload["mimeType"] == "text/plain":
            data = payload["body"].get("data")
            if data:
                body = base64.urlsafe_b64decode(data).decode("utf-8")
        return body

    def _download_attachments(self, service, msg_id: str, payload: dict) -> list[str]:
        attachments_list = []
        if "parts" not in payload:
            return attachments_list

        for part in payload["parts"]:
            filename = part.get("filename")
            body = part.get("body", {})
            attachment_id = body.get("attachmentId")

            if filename and attachment_id:
                msg_dir = settings.attachments_dir / msg_id
                msg_dir.mkdir(parents=True, exist_ok=True)

                attachment = (
                    service.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=msg_id, id=attachment_id)
                    .execute()
                )

                file_data = base64.urlsafe_b64decode(attachment["data"])
                file_path = msg_dir / filename

                with open(file_path, "wb") as f:
                    f.write(file_data)

                attachments_list.append(filename)

            if "parts" in part:
                attachments_list.extend(
                    self._download_attachments(service, msg_id, part)
                )

        return attachments_list

    def _get_or_create_label(self, service, label_name: str = "listed") -> str | None:
        try:
            results = service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])
            for label in labels:
                if label["name"].lower() == label_name.lower():
                    return label["id"]

            label_object = {
                "messageListVisibility": "show",
                "name": label_name,
                "labelListVisibility": "labelShow",
            }
            created = (
                service.users()
                .labels()
                .create(userId="me", body=label_object)
                .execute()
            )
            return created["id"]
        except Exception:
            return None


gmail_service = GmailService()
