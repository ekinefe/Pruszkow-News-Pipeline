import os
from pathlib import Path

from google import genai
from google.genai import types

from backend.config import settings


class GeminiService:
    def __init__(self):
        self._client = None

    def _get_client(self) -> genai.Client:
        if self._client:
            return self._client

        api_key = settings.gemini_api_key
        if not api_key:
            raise RuntimeError("Gemini API key not configured. Set GEMINI_API_KEY in Settings.")

        self._client = genai.Client(api_key=api_key)
        return self._client

    def generate_article(
        self,
        title: str,
        sender: str,
        body: str,
        attachments: list[str] | None = None,
    ) -> dict:
        client = self._get_client()

        attachment_str = ", ".join(attachments) if attachments else "None"
        prompt = (
            f"Email Title: {title}\n"
            f"Sender: {sender}\n"
            f"Attached Files: {attachment_str}\n"
            f"Email Body:\n{body}\n\n"
            "Please write the article now."
        )

        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=settings.system_rules,
            ),
        )

        article_text = response.text
        lines = article_text.strip().split("\n", 1)
        headline = lines[0].strip()
        article_body = lines[1].strip() if len(lines) > 1 else ""

        return {
            "headline": headline,
            "body": article_body,
            "full_text": article_text.strip(),
        }


gemini_service = GeminiService()
