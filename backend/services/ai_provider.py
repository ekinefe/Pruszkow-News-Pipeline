from abc import ABC, abstractmethod
import json
import re
import time

from backend.config import settings

_BATCH_SUFFIX = (
    "\n\nBATCH OUTPUT INSTRUCTIONS:\n"
    "You are receiving multiple emails. Write one article per email.\n"
    "Return your response as a raw JSON array (no markdown fences, no labels).\n"
    'Each object must have: "email_index" (integer, 1-based), "headline" (string), "body" (string with HTML), '
    '"seo_title" (string, max 60 chars), "seo_description" (string, max 160 chars).\n'
    'Example: [{"email_index":1,"headline":"...","body":"<p>...</p>","seo_title":"...","seo_description":"..."}]'
)


def _build_effective_rules() -> str:
    from backend.services.database import database_service
    base = database_service.load_system_rules()

    base = re.sub(r"[Mm]aximum\s+\d+\s+words?\.?", "", base)
    base = re.sub(r"[Mm]inimum\s+\d+\s+words?\.?", "", base)
    base = re.sub(r"\d+\s+words?\s+maximum\.?", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\d+\s+words?\s+minimum\.?", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\n{3,}", "\n\n", base)

    art = database_service.load_article_settings()
    parts = [base.strip()]

    min_w = art.get("min_words", 50)
    max_w = art.get("max_words", 200)
    lang = art.get("language", "polish")

    parts.append(
        f"\n\nCRITICAL WORD COUNT RULE:\n"
        f"You MUST write at least {min_w} words. This is a hard minimum. "
        f"Do NOT stop writing before reaching {min_w} words. "
        f"Count your words mentally and keep writing until you reach the minimum. "
        f"Maximum {max_w} words."
    )

    lang_map = {
        "polish": "Write the article in Polish.",
        "english": "Write the article in English.",
        "auto": "Write the article in the same language as the email body.",
    }
    if lang in lang_map:
        parts.append(f"\n{lang_map[lang]}")

    return "".join(parts)


class AIProvider(ABC):
    @abstractmethod
    def generate_article(
        self,
        title: str,
        sender: str,
        body: str,
        attachments: list[str] | None = None,
    ) -> dict:
        pass

    @abstractmethod
    def generate_articles_batch(self, emails: list[dict]) -> list[dict]:
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    def test_connection(self) -> dict:
        return {"ok": False, "error": "Not implemented"}

    def _build_prompt(
        self,
        title: str,
        sender: str,
        body: str,
        attachments: list[str] | None = None,
    ) -> str:
        attachment_str = ", ".join(attachments) if attachments else "None"
        return (
            f"Email Title: {title}\n"
            f"Sender: {sender}\n"
            f"Attached Files: {attachment_str}\n"
            f"Email Body:\n{body}\n\n"
            "Please write the article now."
        )

    def _parse_response(self, text: str) -> dict:
        seo_title = ""
        seo_description = ""

        # Extract SEO fields if present
        lines = text.strip().split("\n")
        filtered_lines = []
        for line in lines:
            if line.strip().upper().startswith("SEO_TITLE:"):
                seo_title = line.strip()[len("SEO_TITLE:"):].strip().strip('"').strip("'")
            elif line.strip().upper().startswith("SEO_DESCRIPTION:"):
                seo_description = line.strip()[len("SEO_DESCRIPTION:"):].strip().strip('"').strip("'")
            else:
                filtered_lines.append(line)

        # Parse headline and body from remaining lines
        text_cleaned = "\n".join(filtered_lines).strip()
        parts = text_cleaned.split("\n", 1)
        headline = parts[0].strip()
        article_body = parts[1].strip() if len(parts) > 1 else ""

        return {
            "headline": headline,
            "body": article_body,
            "seo_title": seo_title,
            "seo_description": seo_description,
            "full_text": text.strip(),
        }

    def _build_batch_prompt(self, emails: list[dict]) -> str:
        parts = []
        for i, email in enumerate(emails, 1):
            attachment_str = ", ".join(email.get("attachments", [])) or "None"
            parts.append(
                f"--- Email {i} ---\n"
                f"Title: {email['title']}\n"
                f"Sender: {email['sender']}\n"
                f"Attachments: {attachment_str}\n"
                f"Body:\n{email['body']}"
            )
        return "\n\n".join(parts)

    def _parse_batch_response(self, text: str) -> list[dict]:
        if not text or not text.strip():
            raise ValueError("AI returned empty response (possible safety filter block or API error)")
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            preview = cleaned[:300] + ("..." if len(cleaned) > 300 else "")
            raise ValueError(f"AI did not return valid JSON ({e}). Response preview: {preview}")
        if not isinstance(data, list):
            raise ValueError("Expected JSON array from AI, got: " + type(data).__name__)
        return data


class GeminiProvider(AIProvider):
    def __init__(self):
        self._client = None

    def is_configured(self) -> bool:
        return bool(settings.gemini_api_key)

    def _get_client(self):
        if self._client:
            return self._client
        from google import genai
        self._client = genai.Client(api_key=settings.gemini_api_key)
        return self._client

    def generate_article(
        self,
        title: str,
        sender: str,
        body: str,
        attachments: list[str] | None = None,
    ) -> dict:
        from google.genai import types
        from backend.services.usage import usage_service

        client = self._get_client()
        prompt = self._build_prompt(title, sender, body, attachments)
        t0 = time.monotonic()
        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_build_effective_rules(),
                ),
            )
            latency = int((time.monotonic() - t0) * 1000)
            input_tokens = getattr(response, "usage_metadata", None)
            input_tokens = getattr(input_tokens, "prompt_token_count", 0) or 0
            output_tokens = getattr(response, "usage_metadata", None)
            output_tokens = getattr(output_tokens, "candidates_token_count", 0) or 0
            usage_service.record(
                provider="gemini",
                model=settings.gemini_model,
                operation="generate",
                success=True,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency,
            )
            return self._parse_response(response.text)
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            usage_service.record(
                provider="gemini",
                model=settings.gemini_model,
                operation="generate",
                success=False,
                latency_ms=latency,
                error=str(e),
            )
            raise

    def test_connection(self) -> dict:
        from backend.services.usage import usage_service
        t0 = time.monotonic()
        try:
            from google import genai
            client = genai.Client(api_key=settings.gemini_api_key)
            client.models.get(model=settings.gemini_model)
            latency = int((time.monotonic() - t0) * 1000)
            usage_service.record(provider="gemini", model=settings.gemini_model, operation="test", success=True, latency_ms=latency)
            return {"ok": True, "model": settings.gemini_model}
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            usage_service.record(provider="gemini", model=settings.gemini_model, operation="test", success=False, latency_ms=latency, error=str(e))
            return {"ok": False, "error": str(e)}

    def generate_articles_batch(self, emails: list[dict]) -> list[dict]:
        from google.genai import types
        from backend.services.usage import usage_service

        client = self._get_client()
        prompt = self._build_batch_prompt(emails)
        batch_rules = _build_effective_rules() + _BATCH_SUFFIX
        t0 = time.monotonic()
        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=batch_rules,
                ),
            )
            latency = int((time.monotonic() - t0) * 1000)
            input_tokens = getattr(response, "usage_metadata", None)
            input_tokens = getattr(input_tokens, "prompt_token_count", 0) or 0
            output_tokens = getattr(response, "usage_metadata", None)
            output_tokens = getattr(output_tokens, "candidates_token_count", 0) or 0

            response_text = getattr(response, "text", None) or ""

            usage_service.record(
                provider="gemini",
                model=settings.gemini_model,
                operation="generate_batch",
                success=True,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency,
            )
            return self._parse_batch_response(response_text)
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            usage_service.record(
                provider="gemini",
                model=settings.gemini_model,
                operation="generate_batch",
                success=False,
                latency_ms=latency,
                error=str(e),
            )
            raise


class ClaudeProvider(AIProvider):
    def __init__(self):
        self._client = None

    def is_configured(self) -> bool:
        return bool(settings.claude_api_key)

    def _get_client(self):
        if self._client:
            return self._client
        import anthropic
        self._client = anthropic.Anthropic(api_key=settings.claude_api_key)
        return self._client

    def generate_article(
        self,
        title: str,
        sender: str,
        body: str,
        attachments: list[str] | None = None,
    ) -> dict:
        from backend.services.usage import usage_service

        client = self._get_client()
        prompt = self._build_prompt(title, sender, body, attachments)
        t0 = time.monotonic()
        try:
            response = client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                system=_build_effective_rules(),
                messages=[{"role": "user", "content": prompt}],
            )
            latency = int((time.monotonic() - t0) * 1000)
            input_tokens = getattr(response, "usage", None)
            input_tokens = getattr(input_tokens, "input_tokens", 0) or 0
            output_tokens = getattr(response, "usage", None)
            output_tokens = getattr(output_tokens, "output_tokens", 0) or 0
            usage_service.record(
                provider="claude",
                model=settings.claude_model,
                operation="generate",
                success=True,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency,
            )
            text = response.content[0].text
            return self._parse_response(text)
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            usage_service.record(
                provider="claude",
                model=settings.claude_model,
                operation="generate",
                success=False,
                latency_ms=latency,
                error=str(e),
            )
            raise

    def test_connection(self) -> dict:
        from backend.services.usage import usage_service
        t0 = time.monotonic()
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.claude_api_key)
            client.messages.create(
                model=settings.claude_model,
                max_tokens=32,
                messages=[{"role": "user", "content": "Say OK"}],
            )
            latency = int((time.monotonic() - t0) * 1000)
            usage_service.record(provider="claude", model=settings.claude_model, operation="test", success=True, latency_ms=latency)
            return {"ok": True, "model": settings.claude_model}
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            usage_service.record(provider="claude", model=settings.claude_model, operation="test", success=False, latency_ms=latency, error=str(e))
            return {"ok": False, "error": str(e)}

    def generate_articles_batch(self, emails: list[dict]) -> list[dict]:
        from backend.services.usage import usage_service

        client = self._get_client()
        prompt = self._build_batch_prompt(emails)
        batch_rules = _build_effective_rules() + _BATCH_SUFFIX
        t0 = time.monotonic()
        try:
            response = client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                system=batch_rules,
                messages=[{"role": "user", "content": prompt}],
            )
            latency = int((time.monotonic() - t0) * 1000)
            input_tokens = getattr(response, "usage", None)
            input_tokens = getattr(input_tokens, "input_tokens", 0) or 0
            output_tokens = getattr(response, "usage", None)
            output_tokens = getattr(output_tokens, "output_tokens", 0) or 0
            usage_service.record(
                provider="claude",
                model=settings.claude_model,
                operation="generate_batch",
                success=True,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency,
            )
            text = response.content[0].text
            return self._parse_batch_response(text)
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            usage_service.record(
                provider="claude",
                model=settings.claude_model,
                operation="generate_batch",
                success=False,
                latency_ms=latency,
                error=str(e),
            )
            raise


class OpenAIProvider(AIProvider):
    def __init__(self):
        self._client = None

    def is_configured(self) -> bool:
        return bool(settings.openai_api_key)

    def _get_client(self):
        if self._client:
            return self._client
        import openai
        self._client = openai.OpenAI(api_key=settings.openai_api_key)
        return self._client

    def generate_article(
        self,
        title: str,
        sender: str,
        body: str,
        attachments: list[str] | None = None,
    ) -> dict:
        from backend.services.usage import usage_service

        client = self._get_client()
        prompt = self._build_prompt(title, sender, body, attachments)
        t0 = time.monotonic()
        try:
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": _build_effective_rules()},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=4096,
            )
            latency = int((time.monotonic() - t0) * 1000)
            usage_obj = getattr(response, "usage", None)
            input_tokens = getattr(usage_obj, "prompt_tokens", 0) or 0
            output_tokens = getattr(usage_obj, "completion_tokens", 0) or 0
            usage_service.record(
                provider="openai",
                model=settings.openai_model,
                operation="generate",
                success=True,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency,
            )
            text = response.choices[0].message.content
            return self._parse_response(text)
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            usage_service.record(
                provider="openai",
                model=settings.openai_model,
                operation="generate",
                success=False,
                latency_ms=latency,
                error=str(e),
            )
            raise

    def test_connection(self) -> dict:
        from backend.services.usage import usage_service
        t0 = time.monotonic()
        try:
            import openai
            client = openai.OpenAI(api_key=settings.openai_api_key)
            client.models.retrieve(model=settings.openai_model)
            latency = int((time.monotonic() - t0) * 1000)
            usage_service.record(provider="openai", model=settings.openai_model, operation="test", success=True, latency_ms=latency)
            return {"ok": True, "model": settings.openai_model}
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            usage_service.record(provider="openai", model=settings.openai_model, operation="test", success=False, latency_ms=latency, error=str(e))
            return {"ok": False, "error": str(e)}

    def generate_articles_batch(self, emails: list[dict]) -> list[dict]:
        from backend.services.usage import usage_service

        client = self._get_client()
        prompt = self._build_batch_prompt(emails)
        batch_rules = settings.system_rules + _BATCH_SUFFIX
        t0 = time.monotonic()
        try:
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": batch_rules},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=4096,
            )
            latency = int((time.monotonic() - t0) * 1000)
            usage_obj = getattr(response, "usage", None)
            input_tokens = getattr(usage_obj, "prompt_tokens", 0) or 0
            output_tokens = getattr(usage_obj, "completion_tokens", 0) or 0
            usage_service.record(
                provider="openai",
                model=settings.openai_model,
                operation="generate_batch",
                success=True,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency,
            )
            text = response.choices[0].message.content
            return self._parse_batch_response(text)
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            usage_service.record(
                provider="openai",
                model=settings.openai_model,
                operation="generate_batch",
                success=False,
                latency_ms=latency,
                error=str(e),
            )
            raise


providers = {
    "gemini": GeminiProvider,
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
}


def get_provider(name: str | None = None) -> AIProvider:
    provider_name = name or settings.ai_provider
    cls = providers.get(provider_name)
    if not cls:
        raise ValueError(f"Unknown AI provider: {provider_name}")
    return cls()


def get_provider_status() -> dict:
    result = {}
    for name, cls in providers.items():
        provider = cls()
        result[name] = {
            "configured": provider.is_configured(),
            "active": name == settings.ai_provider,
        }
    return result
