import json
import os
from datetime import datetime, timedelta
from typing import Literal, Optional

import resend
from agency_swarm.tools import BaseTool
from pydantic import Field, validator
from dotenv import load_dotenv

load_dotenv()


class ResendEmailTool(BaseTool):
    """
    Send and manage emails via Resend. Supports single send, batch send, retrieval, update (e.g., scheduled_at),
    cancel, list, and attachment operations.
    """

    operation: Literal[
        "send_email",
        "send_batch",
        "get_email",
        "update_email",
        "cancel_email",
        "list_emails",
        "list_attachments",
        "get_attachment",
    ] = Field(..., description="Which Resend action to perform.")

    # Common fields
    from_email: Optional[str] = Field(None, description="Sender in format 'Name <email@domain>' for sends.")
    to: Optional[list[str]] = Field(None, description="Recipient list for single send.")
    subject: Optional[str] = Field(None, description="Subject line for send/update.")
    html: Optional[str] = Field(None, description="HTML body for send.")
    text: Optional[str] = Field(None, description="Plain text body for send (optional).")
    scheduled_at: Optional[str] = Field(None, description="ISO timestamp for scheduling/rescheduling.")

    # Batch payload provided as JSON string list of email param dicts
    batch_payload_json: Optional[str] = Field(
        None,
        description="JSON list of email param dicts for batch send. Each item should include from, to, subject, and html/text.",
    )

    email_id: Optional[str] = Field(None, description="Email id for get/update/cancel/list_attachments/get_attachment.")
    attachment_id: Optional[str] = Field(None, description="Attachment id for get_attachment.")

    @validator("scheduled_at")
    def _validate_iso_datetime(cls, v):
        if v is None:
            return v
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"scheduled_at must be ISO8601: {exc}") from exc
        return v

    def run(self) -> str:
        api_key = os.getenv("RESEND_API_KEY")
        if not api_key:
            raise ValueError("Missing RESEND_API_KEY in environment.")
        resend.api_key = api_key

        if self.operation == "send_email":
            if not (self.from_email and self.to and self.subject and (self.html or self.text)):
                raise ValueError("from_email, to, subject, and html or text are required for send_email.")
            params = {
                "from": self.from_email,
                "to": self.to,
                "subject": self.subject,
                "html": self.html,
            }
            if self.text:
                params["text"] = self.text
            if self.scheduled_at:
                params["scheduled_at"] = self.scheduled_at
            email = resend.Emails.send(params)
            return f"Sent email id: {email['id']} to {', '.join(self.to)}."

        if self.operation == "send_batch":
            if not self.batch_payload_json:
                raise ValueError("batch_payload_json is required for send_batch.")
            payload = self._parse_batch(self.batch_payload_json)
            emails = resend.Batch.send(payload)
            return f"Batch send triggered for {len(payload)} messages. Response: {emails}"

        if self.operation == "get_email":
            if not self.email_id:
                raise ValueError("email_id is required for get_email.")
            email = resend.Emails.get(email_id=self.email_id)
            return f"Email {self.email_id} status: {email.get('status')}"

        if self.operation == "update_email":
            if not (self.email_id and self.scheduled_at):
                raise ValueError("email_id and scheduled_at are required for update_email.")
            update_params = {"id": self.email_id, "scheduled_at": self.scheduled_at}
            result = resend.Emails.update(params=update_params)
            return f"Updated email {self.email_id} schedule to {self.scheduled_at}. Response: {result}"

        if self.operation == "cancel_email":
            if not self.email_id:
                raise ValueError("email_id is required for cancel_email.")
            result = resend.Emails.cancel(email_id=self.email_id)
            return f"Canceled email {self.email_id}. Response: {result}"

        if self.operation == "list_emails":
            emails = resend.Emails.list()
            count = len(emails.get("data", [])) if isinstance(emails, dict) else len(emails or [])
            return f"Listed {count} emails."

        if self.operation == "list_attachments":
            if not self.email_id:
                raise ValueError("email_id is required for list_attachments.")
            attachments = resend.Emails.Attachments.list(email_id=self.email_id)
            count = len(attachments.get("data", [])) if isinstance(attachments, dict) else len(attachments or [])
            return f"Email {self.email_id} attachments: {count} found."

        if self.operation == "get_attachment":
            if not (self.email_id and self.attachment_id):
                raise ValueError("email_id and attachment_id are required for get_attachment.")
            attachment = resend.Emails.Attachments.get(email_id=self.email_id, attachment_id=self.attachment_id)
            return f"Fetched attachment {self.attachment_id} for email {self.email_id}. Size: {len(attachment or {})} bytes."

        raise ValueError(f"Unsupported operation: {self.operation}")

    def _parse_batch(self, raw: str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in batch_payload_json: {exc}") from exc
        if not isinstance(payload, list):
            raise ValueError("batch_payload_json must be a JSON list of email param dictionaries.")
        return payload


if __name__ == "__main__":
    # Simple sanity check (won't send without valid API key/addresses)
    tool = ResendEmailTool(operation="list_emails")
    try:
        print(tool.run())
    except Exception as exc:  # pragma: no cover - manual run aid
        print(f"(Expected without API key) {exc}")
