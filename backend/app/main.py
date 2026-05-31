import json
import os
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


@app.get("/api/status")
def status() -> dict[str, object]:
    return {
        "status": "ok",
        "llm_provider": "deepseek" if settings.deepseek_api_key else ("openai" if settings.openai_api_key else "local-fallback"),
        "llm_model": settings.llm_model if settings.llm_api_key else None,
        "deepseek_key_present": bool(settings.deepseek_api_key),
        "openai_key_present": bool(settings.openai_api_key),
        "railway_commit": os.getenv("RAILWAY_GIT_COMMIT_SHA"),
    }


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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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


def fallback_answer(question: str, contexts: list[dict], error: str | None = None) -> str:
    if not contexts:
        return (
            "I could not find relevant knowledge-base context for this question. "
            "Try uploading a document or selecting a different knowledge item."
        )

    lines = [
        "I found relevant passages, but the LLM generation step failed. Here is a retrieval-based summary:",
        "",
    ]
    if error:
        lines.extend([f"LLM error: {error[:360]}", ""])
    for item in contexts[:3]:
        excerpt = " ".join(item["text"].split())[:520]
        lines.append(f"[{item['rank']}] {item['title']}: {excerpt}")
    lines.append("")
    lines.append("Check the backend LLM API key/settings if you expected a generated answer.")
    return "\n".join(lines)


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
        try:
            async for token in stream_answer(payload.question, history, contexts):
                answer_parts.append(token)
                yield sse("token", {"token": token})
        except Exception as exc:
            error_message = str(exc)
            answer = fallback_answer(payload.question, contexts, error_message)
            answer_parts = [answer]
            yield sse("token", {"token": answer})
            yield sse("error", {"message": f"LLM generation failed: {error_message}"})
        answer = "".join(answer_parts).strip()
        add_message(conversation_id, "assistant", answer)
        yield sse("done", {"answer": answer, "conversation_id": conversation_id})

    return StreamingResponse(events(), media_type="text/event-stream")
