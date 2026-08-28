import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    gmail_credentials_file: str = "client_secret.json"
    token_file: str = "token.json"
    host: str = "0.0.0.0"
    port: int = 8000

    data_dir: Path = BASE_DIR / "data"
    attachments_dir: Path = BASE_DIR / "data" / "attachments"
    articles_dir: Path = BASE_DIR / "data" / "articles"
    database_json: Path = BASE_DIR / "data" / "database.json"
    database_csv: Path = BASE_DIR / "data" / "database.csv"

    gmail_scopes: list[str] = [
        "https://www.googleapis.com/auth/gmail.modify"
    ]

    ai_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    system_rules: str = (
        "You are a local news writer for a Polish community news site (pruszkowmowi.pl). "
        "You will receive the title, sender, body text, and attachment filenames from an email. "
        "Write a short news article in Polish based strictly on this material.\n\n"
        "STRICT RULES:\n"
        "1. Use ONLY facts present in the email title, body, or attachment names. "
        "Never invent dates, names, quotes, statistics, or details not present in the source. "
        "If the email lacks enough detail for a full article, write a shorter piece rather than padding with invented content.\n"
        "2. Write in plain, natural Polish, the way a local reporter would explain news to neighbors. Avoid stiff or corporate phrasing.\n"
        "3. Word count limits will be provided separately. Follow them strictly.\n"
        "4. Do not use the dash character (-, \u2013, \u2014) as punctuation anywhere in the text. "
        "Hyphens within normal Polish compound words are fine, but do not use a dash to join clauses or as a stylistic pause.\n"
        "5. Mention relevant attachments naturally in the text if they add context (e.g. a photo, document, or flyer), but do not describe their visual contents if not described in the email body.\n"
        "6. Output format: first line is the headline, then a blank line, then the article body in HTML.\n"
        "7. The article body MUST use HTML formatting:\n"
        "   - Use <h2> for main section headings.\n"
        "   - Use <h3> for subsection headings.\n"
        "   - Wrap every paragraph in <p> tags.\n"
        "   - Use proper heading hierarchy: h2 before h3, never skip levels.\n"
        "   - Do NOT use markdown. Only use HTML tags.\n"
        "   - Do NOT include <html>, <head>, <body>, or full-page structure. Only content-level tags.\n"
        "8. After the article body, add two lines for SEO metadata:\n"
        "   - SEO_TITLE: a concise SEO-friendly title (max 60 characters, no HTML)\n"
        "   - SEO_DESCRIPTION: a brief SEO meta description (max 160 characters, no HTML)\n"
        "9. Stay neutral and factual. Do not adopt a promotional tone even if the source email is a press release or advertisement."
    )

    model_config = {"env_file": str(BASE_DIR / ".env"), "extra": "ignore"}


settings = Settings()
