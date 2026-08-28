from pydantic import BaseModel


class EmailRecord(BaseModel):
    id: str
    sender: str
    title: str
    date: str
    body: str
    attachments: list[str] = []


class EmailFetchRequest(BaseModel):
    max_results: int = 10
    query: str = ""
    mark_read: bool = False
    add_label: bool = False


class ArticleRecord(BaseModel):
    id: str
    email_id: str
    headline: str
    body: str
    filename: str


class ArticleUpdate(BaseModel):
    headline: str | None = None
    body: str | None = None


class GenerateRequest(BaseModel):
    email_ids: list[str]
    mode: str = "batch"


class CreateDraftsRequest(BaseModel):
    articles: list[dict]


class DraftArticle(BaseModel):
    article_id: str
    headline: str
    body: str
    email_id: str
