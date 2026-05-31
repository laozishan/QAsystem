from pydantic import BaseModel, Field, HttpUrl


class DocumentOut(BaseModel):
    id: str
    title: str
    source: str
    created_at: str


class WebIngestRequest(BaseModel):
    url: HttpUrl
    title: str | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    document_id: str | None = None


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str

