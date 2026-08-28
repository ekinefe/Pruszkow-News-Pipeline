import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from backend.config import settings, BASE_DIR
from backend.services.gmail import gmail_service
from backend.services.database import database_service
from backend.services.ai_provider import get_provider_status
from backend.services.usage import usage_service

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
def get_settings():
    return {
        "gmail_credentials_file": settings.gmail_credentials_file,
        "host": settings.host,
        "port": settings.port,
        "ai_provider": settings.ai_provider,
        "providers": get_provider_status(),
        "gemini_model": settings.gemini_model,
        "claude_model": settings.claude_model,
        "openai_model": settings.openai_model,
        "system_rules": database_service.load_system_rules(),
    }


@router.get("/settings/credentials")
def get_credentials_status():
    cred_path = Path(settings.gmail_credentials_file)
    if not cred_path.is_absolute():
        cred_path = BASE_DIR / cred_path
    exists = cred_path.exists()
    info = {}
    if exists:
        try:
            with open(cred_path, "r") as f:
                data = json.load(f)
            if "installed" in data:
                info["type"] = "Desktop App"
            elif "web" in data:
                info["type"] = "Web App"
            elif "service_account" in data:
                info["type"] = "Service Account"
            else:
                info["type"] = "Unknown"
        except Exception:
            info["type"] = "Invalid JSON"
    return {"exists": exists, "path": str(cred_path), **info}


@router.post("/settings/credentials")
async def upload_credentials(file: UploadFile = File(...)):
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be a .json file")

    content = await file.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    if "installed" not in data and "web" not in data and "service_account" not in data:
        raise HTTPException(
            status_code=400,
            detail="Invalid credentials file. Must contain 'installed', 'web', or 'service_account' key.",
        )

    cred_path = Path(settings.gmail_credentials_file)
    if not cred_path.is_absolute():
        cred_path = BASE_DIR / cred_path

    with open(cred_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return {"success": True, "filename": file.filename, "path": str(cred_path)}


class AIProviderRequest(BaseModel):
    provider: str


class APIKeyRequest(BaseModel):
    key: str


@router.post("/settings/ai-provider")
def set_ai_provider(req: AIProviderRequest):
    if req.provider not in ("gemini", "claude", "openai"):
        raise HTTPException(status_code=400, detail="Provider must be gemini, claude, or openai")

    env_path = BASE_DIR / ".env"
    _update_env("AI_PROVIDER", req.provider)

    settings.ai_provider = req.provider
    return {"provider": req.provider, "providers": get_provider_status()}


@router.post("/settings/api-key")
def set_api_key(req: APIKeyRequest, provider: str = ""):
    if not provider:
        provider = settings.ai_provider

    if provider not in ("gemini", "claude", "openai"):
        raise HTTPException(status_code=400, detail="Invalid provider")

    env_key_map = {
        "gemini": "GEMINI_API_KEY",
        "claude": "CLAUDE_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    config_key_map = {
        "gemini": "gemini_api_key",
        "claude": "claude_api_key",
        "openai": "openai_api_key",
    }

    env_var = env_key_map[provider]
    config_var = config_key_map[provider]

    _update_env(env_var, req.key)
    setattr(settings, config_var, req.key)

    return {"provider": provider, "configured": bool(req.key)}


@router.get("/settings/api-key")
def get_api_key_status(provider: str = ""):
    if not provider:
        provider = settings.ai_provider

    status = get_provider_status()
    return {
        "provider": provider,
        "configured": status.get(provider, {}).get("configured", False),
    }


@router.post("/settings/test-key")
def test_api_key(provider: str):
    if provider not in ("gemini", "claude", "openai"):
        raise HTTPException(status_code=400, detail="Invalid provider")

    key_map = {
        "gemini": "gemini_api_key",
        "claude": "claude_api_key",
        "openai": "openai_api_key",
    }
    key = getattr(settings, key_map[provider], "")
    if not key:
        return {"ok": False, "error": "No API key configured for this provider"}

    from backend.services.ai_provider import providers as provider_classes
    try:
        p = provider_classes[provider]()
        return p.test_connection()
    except Exception as e:
        return {"ok": False, "error": str(e)}


# --- System Rules ---

class SystemRulesRequest(BaseModel):
    rules: str


@router.get("/settings/system-rules")
def get_system_rules():
    return {"rules": database_service.load_system_rules()}


@router.post("/settings/system-rules")
def set_system_rules(req: SystemRulesRequest):
    database_service.save_system_rules(req.rules)
    settings.system_rules = req.rules
    return {"saved": True}


# --- Article Settings ---

class ArticleSettingsRequest(BaseModel):
    min_words: int | None = None
    max_words: int | None = None
    language: str | None = None
    default_mode: str | None = None


@router.get("/settings/article-settings")
def get_article_settings():
    return database_service.load_article_settings()


@router.post("/settings/article-settings")
def set_article_settings(req: ArticleSettingsRequest):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if "min_words" in data and data["min_words"] < 0:
        raise HTTPException(status_code=400, detail="min_words must be >= 0")
    if "max_words" in data and data["max_words"] < 1:
        raise HTTPException(status_code=400, detail="max_words must be >= 1")
    if "min_words" in data and "max_words" in data:
        if data["min_words"] > data["max_words"]:
            raise HTTPException(status_code=400, detail="min_words cannot exceed max_words")
    if "language" in data and data["language"] not in ("polish", "english", "auto"):
        raise HTTPException(status_code=400, detail="language must be polish, english, or auto")
    if "default_mode" in data and data["default_mode"] not in ("batch", "single"):
        raise HTTPException(status_code=400, detail="default_mode must be batch or single")
    database_service.save_article_settings(data)
    return database_service.load_article_settings()


# --- Usage & Dashboard ---

@router.get("/usage")
def get_usage(provider: str = "", since: str = "", limit: int = 500):
    records = usage_service.get_records(provider=provider, since=since, limit=limit)
    return {"records": records, "count": len(records)}


@router.get("/usage/summary")
def get_usage_summary(provider: str = ""):
    return usage_service.get_summary(provider=provider)


class QuotaRequest(BaseModel):
    daily_requests: int | None = None
    weekly_requests: int | None = None
    monthly_requests: int | None = None
    daily_tokens: int | None = None
    weekly_tokens: int | None = None
    monthly_tokens: int | None = None


@router.get("/usage/quota")
def get_quota():
    return usage_service.get_quota()


@router.post("/usage/quota")
def set_quota(req: QuotaRequest):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    usage_service.set_quota(data)
    return usage_service.get_quota()


@router.post("/usage/reset")
def reset_usage():
    usage_service.reset_usage()
    return {"reset": True}


# --- Auth ---

@router.post("/auth/start")
def start_auth():
    result = gmail_service.authenticate()
    return result


@router.get("/auth/status")
def auth_status():
    authenticated = gmail_service.is_authenticated()
    return {
        "authenticated": authenticated,
        "email": gmail_service.get_user_email() if authenticated else None,
    }


@router.get("/status")
def pipeline_status():
    stats = database_service.get_stats()
    return {
        "authenticated": gmail_service.is_authenticated(),
        **stats,
    }


# --- Ignored Senders ---

class IgnoredSenderRequest(BaseModel):
    sender: str


@router.get("/settings/ignored")
def get_ignored_senders():
    senders = database_service.load_ignored_senders()
    return {"senders": senders, "count": len(senders)}


@router.post("/settings/ignored")
def add_ignored_sender(req: IgnoredSenderRequest):
    if not req.sender.strip():
        raise HTTPException(status_code=400, detail="Sender cannot be empty")
    senders = database_service.add_ignored_sender(req.sender.strip())
    return {"senders": senders, "count": len(senders)}


@router.delete("/settings/ignored/{sender}")
def remove_ignored_sender(sender: str):
    senders = database_service.remove_ignored_sender(sender)
    return {"senders": senders, "count": len(senders)}


# --- Helpers ---

def _update_env(key: str, value: str):
    env_path = BASE_DIR / ".env"
    lines = []
    found = False
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if line.strip().startswith(f"{key}="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"{key}={value}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)
    os.environ[key] = value
