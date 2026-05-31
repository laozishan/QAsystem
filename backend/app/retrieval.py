import hashlib
import json
import math
import re
import uuid
from typing import Any

from openai import OpenAI

from .config import settings

try:
    import chromadb
except ImportError:
    chromadb = None


TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
EMBEDDING_DIMS = 384


def local_embed(text: str, dims: int = EMBEDDING_DIMS) -> list[float]:
    vector = [0.0] * dims
    tokens = TOKEN_RE.findall(text.lower())
    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if settings.openai_api_key:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(model=settings.embedding_model, input=texts)
        return [item.embedding for item in response.data]
    return [local_embed(text) for text in texts]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


class JsonVectorStore:
    def __init__(self) -> None:
        self.path = settings.chroma_path.parent / "vector_chunks.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, items: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_chunks(self, document_id: str, title: str, source: str, chunks: list[str]) -> int:
        items = self._read()
        embeddings = embed_texts(chunks)
        for index, chunk in enumerate(chunks):
            items.append(
                {
                    "id": str(uuid.uuid4()),
                    "document": chunk,
                    "embedding": embeddings[index],
                    "metadata": {
                        "document_id": document_id,
                        "title": title,
                        "source": source,
                        "chunk_index": index,
                    },
                }
            )
        self._write(items)
        return len(chunks)

    def query(self, question: str, document_id: str | None = None, k: int | None = None) -> list[dict[str, Any]]:
        query_embedding = embed_texts([question])[0]
        scored = []
        for item in self._read():
            metadata = item["metadata"]
            if document_id and metadata.get("document_id") != document_id:
                continue
            scored.append((cosine(query_embedding, item["embedding"]), item))
        scored.sort(key=lambda pair: pair[0], reverse=True)

        contexts: list[dict[str, Any]] = []
        for index, (score, item) in enumerate(scored[: k or settings.retrieval_k]):
            metadata = item["metadata"]
            contexts.append(
                {
                    "rank": index + 1,
                    "text": item["document"],
                    "score": score,
                    "document_id": metadata.get("document_id"),
                    "title": metadata.get("title", "Untitled"),
                    "source": metadata.get("source", ""),
                    "chunk_index": metadata.get("chunk_index", index),
                }
            )
        return contexts

    def delete_document(self, document_id: str) -> None:
        self._write([item for item in self._read() if item["metadata"].get("document_id") != document_id])


class ChromaVectorStore:
    def __init__(self) -> None:
        if chromadb is None:
            raise RuntimeError("chromadb is not installed")
        self.client = chromadb.PersistentClient(path=str(settings.chroma_path))
        self.collection = self.client.get_or_create_collection(name="knowledge_chunks")

    def add_chunks(self, document_id: str, title: str, source: str, chunks: list[str]) -> int:
        if not chunks:
            return 0
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas: list[dict[str, Any]] = [
            {
                "document_id": document_id,
                "title": title,
                "source": source,
                "chunk_index": index,
            }
            for index in range(len(chunks))
        ]
        self.collection.add(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
            embeddings=embed_texts(chunks),
        )
        return len(chunks)

    def query(self, question: str, document_id: str | None = None, k: int | None = None) -> list[dict[str, Any]]:
        where = {"document_id": document_id} if document_id else None
        result = self.collection.query(
            query_embeddings=embed_texts([question]),
            n_results=k or settings.retrieval_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        contexts: list[dict[str, Any]] = []
        for index, document in enumerate(documents):
            metadata = metadatas[index] or {}
            contexts.append(
                {
                    "rank": index + 1,
                    "text": document,
                    "score": 1 - float(distances[index]) if index < len(distances) else None,
                    "document_id": metadata.get("document_id"),
                    "title": metadata.get("title", "Untitled"),
                    "source": metadata.get("source", ""),
                    "chunk_index": metadata.get("chunk_index", index),
                }
            )
        return contexts

    def delete_document(self, document_id: str) -> None:
        self.collection.delete(where={"document_id": document_id})


vector_store = ChromaVectorStore() if chromadb is not None else JsonVectorStore()
