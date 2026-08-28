import json
import csv
from pathlib import Path

from backend.config import settings


class DatabaseService:
    def __init__(self):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.articles_dir.mkdir(parents=True, exist_ok=True)
        settings.attachments_dir.mkdir(parents=True, exist_ok=True)
        self._ignored_senders_path = settings.data_dir / "ignored_senders.json"
        self._system_rules_path = settings.data_dir / "system_rules.json"
        self._article_settings_path = settings.data_dir / "article_settings.json"

    def load_emails(self) -> list[dict]:
        db_path = settings.database_json
        if not db_path.exists():
            return []
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def save_emails(self, emails: list[dict]):
        with open(settings.database_json, "w", encoding="utf-8") as f:
            json.dump(emails, f, ensure_ascii=False, indent=4)

        fieldnames = ["id", "sender", "title", "date", "body", "attachments"]
        with open(settings.database_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(emails)

    def get_email_by_id(self, email_id: str) -> dict | None:
        emails = self.load_emails()
        for e in emails:
            if e["id"] == email_id:
                return e
        return None

    def list_articles(self) -> list[dict]:
        articles = []
        articles_dir = settings.articles_dir
        if not articles_dir.exists():
            return articles

        for file_path in articles_dir.glob("*.txt"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                lines = content.strip().split("\n", 1)
                headline = lines[0].strip() if lines else file_path.stem
                body = lines[1].strip() if len(lines) > 1 else ""

                parts = file_path.stem.rsplit("_", 1)
                email_id = parts[1] if len(parts) > 1 else ""

                articles.append(
                    {
                        "id": file_path.stem,
                        "email_id": email_id,
                        "headline": headline,
                        "body": body,
                        "filename": file_path.name,
                    }
                )
            except (IOError, UnicodeDecodeError):
                continue

        return articles

    def get_article(self, article_id: str) -> dict | None:
        file_path = settings.articles_dir / f"{article_id}.txt"
        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.strip().split("\n", 1)
        headline = lines[0].strip() if lines else ""
        body = lines[1].strip() if len(lines) > 1 else ""

        parts = article_id.rsplit("_", 1)
        email_id = parts[1] if len(parts) > 1 else ""

        return {
            "id": article_id,
            "email_id": email_id,
            "headline": headline,
            "body": body,
            "filename": f"{article_id}.txt",
        }

    def save_article(
        self, email_id: str, title: str, headline: str, body: str,
        seo_title: str = "", seo_description: str = "",
    ) -> dict:
        safe_title = "".join(c for c in title if c.isalnum() or c in " _").strip()
        filename = f"{safe_title[:30]}_{email_id}.txt"
        file_path = settings.articles_dir / filename

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"{headline}\n\n{body}")

        return {
            "id": filename.replace(".txt", ""),
            "email_id": email_id,
            "headline": headline,
            "body": body,
            "seo_title": seo_title,
            "seo_description": seo_description,
            "filename": filename,
        }

    def update_article(self, article_id: str, headline: str | None = None, body: str | None = None) -> dict | None:
        article = self.get_article(article_id)
        if not article:
            return None

        new_headline = headline if headline is not None else article["headline"]
        new_body = body if body is not None else article["body"]

        file_path = settings.articles_dir / f"{article_id}.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"{new_headline}\n\n{new_body}")

        return {
            **article,
            "headline": new_headline,
            "body": new_body,
        }

    def delete_article(self, article_id: str) -> bool:
        file_path = settings.articles_dir / f"{article_id}.txt"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def load_ignored_senders(self) -> list[str]:
        if not self._ignored_senders_path.exists():
            return []
        try:
            with open(self._ignored_senders_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def save_ignored_senders(self, senders: list[str]):
        with open(self._ignored_senders_path, "w", encoding="utf-8") as f:
            json.dump(senders, f, ensure_ascii=False, indent=2)

    def add_ignored_sender(self, sender: str) -> list[str]:
        ignored = self.load_ignored_senders()
        if sender not in ignored:
            ignored.append(sender)
            self.save_ignored_senders(ignored)
        return ignored

    def remove_ignored_sender(self, sender: str) -> list[str]:
        ignored = self.load_ignored_senders()
        ignored = [s for s in ignored if s != sender]
        self.save_ignored_senders(ignored)
        return ignored

    def is_sender_ignored(self, sender: str) -> bool:
        ignored = self.load_ignored_senders()
        sender_lower = sender.lower()
        return any(ign.lower() in sender_lower for ign in ignored)

    def filter_ignored(self, emails: list[dict]) -> list[dict]:
        return [e for e in emails if not self.is_sender_ignored(e.get("sender", ""))]

    def load_system_rules(self) -> str:
        if not self._system_rules_path.exists():
            return settings.system_rules
        try:
            with open(self._system_rules_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("rules", settings.system_rules)
        except (json.JSONDecodeError, IOError):
            return settings.system_rules

    def save_system_rules(self, rules: str):
        with open(self._system_rules_path, "w", encoding="utf-8") as f:
            json.dump({"rules": rules}, f, ensure_ascii=False, indent=2)
        settings.system_rules = rules

    def get_stats(self) -> dict:
        emails = self.load_emails()
        articles = self.list_articles()

        attachments_count = 0
        if settings.attachments_dir.exists():
            for d in settings.attachments_dir.iterdir():
                if d.is_dir():
                    attachments_count += len(list(d.glob("*")))

        return {
            "emails_in_database": len(emails),
            "articles_generated": len(articles),
            "attachments_count": attachments_count,
        }

    _DEFAULT_ARTICLE_SETTINGS = {
        "min_words": 50,
        "max_words": 200,
        "language": "polish",
        "default_mode": "batch",
    }

    def load_article_settings(self) -> dict:
        if not self._article_settings_path.exists():
            return dict(self._DEFAULT_ARTICLE_SETTINGS)
        try:
            with open(self._article_settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = {**self._DEFAULT_ARTICLE_SETTINGS, **data}
            return merged
        except (json.JSONDecodeError, IOError):
            return dict(self._DEFAULT_ARTICLE_SETTINGS)

    def save_article_settings(self, data: dict):
        current = self.load_article_settings()
        current.update({k: v for k, v in data.items() if v is not None})
        with open(self._article_settings_path, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)


database_service = DatabaseService()
