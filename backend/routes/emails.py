import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.models import EmailFetchRequest, GenerateRequest, CreateDraftsRequest
from backend.services.gmail import gmail_service
from backend.services.database import database_service
from backend.services.ai_provider import get_provider

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("")
def list_emails():
    emails = database_service.load_emails()
    emails = database_service.filter_ignored(emails)
    return {"emails": emails, "count": len(emails)}


@router.get("/{email_id}")
def get_email(email_id: str):
    email = database_service.get_email_by_id(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    return email


@router.post("/fetch")
def fetch_emails(req: EmailFetchRequest):
    try:
        emails = gmail_service.fetch_emails(
            max_results=req.max_results,
            query=req.query,
            mark_read=req.mark_read,
            add_label=req.add_label,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    existing = database_service.load_emails()
    existing_ids = {e["id"] for e in existing}
    new_emails = [e for e in emails if e["id"] not in existing_ids]
    all_emails = new_emails + existing
    all_emails = database_service.filter_ignored(all_emails)
    database_service.save_emails(all_emails)

    return {
        "fetched": len(emails),
        "new": len(new_emails),
        "total": len(all_emails),
        "emails": emails,
    }


@router.post("/generate-stream")
def generate_articles_stream(req: GenerateRequest):
    ai = get_provider()

    async def event_generator():
        total = len(req.email_ids)
        generated_articles = []

        emails = []
        missing_ids = []
        for email_id in req.email_ids:
            email = database_service.get_email_by_id(email_id)
            if not email:
                missing_ids.append(email_id)
            else:
                emails.append({"id": email_id, **email})

        for mid in missing_ids:
            yield f"data: {json.dumps({'type': 'error', 'email_id': mid, 'message': 'Email not found', 'current': 0, 'total': total})}\n\n"

        if not emails:
            yield f"data: {json.dumps({'type': 'complete', 'articles': [], 'count': 0})}\n\n"
            return

        if req.mode == "single":
            for i, email in enumerate(emails):
                yield f"data: {json.dumps({'type': 'start', 'email_id': email['id'], 'title': email['title'], 'current': i+1, 'total': total})}\n\n"
                await asyncio.sleep(0.1)
                try:
                    article_data = ai.generate_article(
                        title=email["title"],
                        sender=email["sender"],
                        body=email["body"],
                        attachments=email.get("attachments", []),
                    )
                    saved = database_service.save_article(
                        email_id=email["id"],
                        title=email["title"],
                        headline=article_data["headline"],
                        body=article_data["body"],
                        seo_title=article_data.get("seo_title", ""),
                        seo_description=article_data.get("seo_description", ""),
                    )
                    generated_articles.append(saved)
                    yield f"data: {json.dumps({'type': 'done', 'email_id': email['id'], 'article': saved, 'current': i+1, 'total': total})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'email_id': email['id'], 'message': str(e), 'current': i+1, 'total': total})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'batch_start', 'count': len(emails), 'total': total})}\n\n"
            await asyncio.sleep(0.1)
            try:
                results = ai.generate_articles_batch(emails)
                results_by_index = {}
                for r in results:
                    idx = r.get("email_index", 0) - 1
                    if 0 <= idx < len(emails):
                        results_by_index[idx] = r
                for i, email in enumerate(emails):
                    r = results_by_index.get(i)
                    if not r:
                        yield f"data: {json.dumps({'type': 'error', 'email_id': email['id'], 'message': 'Article missing from AI response', 'current': i+1, 'total': total})}\n\n"
                        continue
                    saved = database_service.save_article(
                        email_id=email["id"],
                        title=email["title"],
                        headline=r.get("headline", ""),
                        body=r.get("body", ""),
                        seo_title=r.get("seo_title", ""),
                        seo_description=r.get("seo_description", ""),
                    )
                    generated_articles.append(saved)
                    yield f"data: {json.dumps({'type': 'done', 'email_id': email['id'], 'article': saved, 'current': i+1, 'total': total})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'email_id': '', 'message': f'Batch generation failed: {str(e)}', 'current': 0, 'total': total})}\n\n"

        yield f"data: {json.dumps({'type': 'complete', 'articles': generated_articles, 'count': len(generated_articles)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/create-drafts")
def create_drafts(req: CreateDraftsRequest):
    results = []
    for article in req.articles:
        try:
            draft_id = gmail_service.create_draft(
                headline=article["headline"],
                article_body=article["body"],
                original_title=article.get("original_title", ""),
                original_sender=article.get("original_sender", ""),
                seo_title=article.get("seo_title", ""),
                seo_description=article.get("seo_description", ""),
            )
            results.append({
                "article_id": article.get("article_id", ""),
                "status": "ok",
                "draft_id": draft_id,
            })
        except Exception as e:
            results.append({
                "article_id": article.get("article_id", ""),
                "status": "error",
                "error": str(e),
            })

    return {"results": results}
