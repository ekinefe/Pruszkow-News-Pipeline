from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from backend.models import ArticleUpdate
from backend.services.database import database_service

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("")
def list_articles():
    articles = database_service.list_articles()
    return {"articles": articles, "count": len(articles)}


@router.get("/{article_id}")
def get_article(article_id: str):
    article = database_service.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.get("/{article_id}/download")
def download_article(article_id: str):
    article = database_service.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    content = f"{article['headline']}\n\n{article['body']}"
    return PlainTextResponse(
        content=content,
        headers={
            "Content-Disposition": f'attachment; filename="{article["filename"]}"'
        },
    )


@router.put("/{article_id}")
def update_article(article_id: str, req: ArticleUpdate):
    updated = database_service.update_article(article_id, req.headline, req.body)
    if not updated:
        raise HTTPException(status_code=404, detail="Article not found")
    return updated


@router.delete("/{article_id}")
def delete_article(article_id: str):
    deleted = database_service.delete_article(article_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"deleted": True}
