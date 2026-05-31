import asyncio
from collections.abc import AsyncIterator

from openai import OpenAI

from .config import settings


def build_messages(question: str, history: list[dict], contexts: list[dict]) -> list[dict[str, str]]:
    context_block = "\n\n".join(
        f"[{item['rank']}] {item['title']} chunk {item['chunk_index']}\n{item['text']}"
        for item in contexts
    )
    system = (
        "You are an AI knowledge-base assistant. Answer from the supplied context when it is relevant. "
        "Use concise, practical language. Cite sources with bracket numbers like [1]. "
        "If the answer is not in the context, say what is missing and provide a careful general answer."
    )
    messages = [{"role": "system", "content": system}]
    if context_block:
        messages.append({"role": "system", "content": f"Retrieved context:\n{context_block}"})
    for message in history[-8:]:
        messages.append({"role": message["role"], "content": message["content"]})
    messages.append({"role": "user", "content": question})
    return messages


async def stream_answer(question: str, history: list[dict], contexts: list[dict]) -> AsyncIterator[str]:
    if settings.llm_api_key:
        client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        stream = client.chat.completions.create(
            model=settings.llm_model,
            messages=build_messages(question, history, contexts),
            temperature=0.2,
            stream=True,
        )
        for event in stream:
            token = event.choices[0].delta.content or ""
            if token:
                yield token
                await asyncio.sleep(0)
        return

    if contexts:
        intro = "I found relevant passages in the knowledge base. "
        body = " ".join(f"[{item['rank']}] {item['text'][:420]}" for item in contexts[:3])
        answer = intro + body
    else:
        answer = (
            "No knowledge-base context is available yet. Upload a PDF, Markdown, TXT file, "
            "or ingest a web page, then ask again."
        )

    for word in answer.split():
        yield word + " "
        await asyncio.sleep(0.015)
