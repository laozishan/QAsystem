import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import settings
from .ingest import chunk_text, extract_upload, extract_web_page
from .llm import stream_answer
from .models import ChatRequest, DocumentOut, WebIngestRequest
from .retrieval import vector_store
from .storage import (
    add_message,
    create_conversation,
    create_document,
    delete_document as delete_document_record,
    get_messages,
    init_db,
    list_conversations,
    list_documents,
)


app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/documents", response_model=list[DocumentOut])
def documents() -> list[dict]:
    return list_documents()


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)) -> dict:
    content = await file.read()
    try:
        text = extract_upload(file.filename or "upload.txt", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No readable text was found in this document.")

    title = Path(file.filename or "Untitled").name
    document = create_document(title=title, source="upload")
    chunk_count = vector_store.add_chunks(document["id"], title, "upload", chunks)
    return {**document, "chunk_count": chunk_count}


@app.post("/api/documents/web")
async def ingest_web_page(payload: WebIngestRequest) -> dict:
    try:
        discovered_title, text = await extract_web_page(str(payload.url))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read web page: {exc}") from exc

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No readable text was found on this web page.")

    title = payload.title or discovered_title
    document = create_document(title=title, source=str(payload.url))
    chunk_count = vector_store.add_chunks(document["id"], title, str(payload.url), chunks)
    return {**document, "chunk_count": chunk_count}


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str) -> dict[str, bool]:
    vector_store.delete_document(document_id)
    delete_document_record(document_id)
    return {"ok": True}


@app.get("/api/conversations")
def conversations() -> list[dict]:
    return list_conversations()


def sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest) -> StreamingResponse:
    conversation_id = payload.conversation_id
    if not conversation_id:
        conversation_id = create_conversation(payload.question)["id"]

    history = get_messages(conversation_id)
    contexts = vector_store.query(payload.question, payload.document_id)
    add_message(conversation_id, "user", payload.question)

    async def events():
        answer_parts: list[str] = []
        yield sse("meta", {"conversation_id": conversation_id, "citations": contexts})
        async for token in stream_answer(payload.question, history, contexts):
            answer_parts.append(token)
            yield sse("token", {"token": token})
        answer = "".join(answer_parts).strip()
        add_message(conversation_id, "assistant", answer)
        yield sse("done", {"answer": answer, "conversation_id": conversation_id})

    return StreamingResponse(events(), media_type="text/event-stream")
