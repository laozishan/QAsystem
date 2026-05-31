import re
from io import BytesIO
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader


TEXT_SUFFIXES = {".txt", ".md", ".markdown"}


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 180) -> list[str]:
    text = clean_text(text)
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            words = paragraph.split()
            piece = ""
            for word in words:
                candidate = f"{piece} {word}".strip()
                if len(candidate) > max_chars and piece:
                    chunks.append(piece)
                    piece = piece[-overlap:] + " " + word if overlap else word
                else:
                    piece = candidate
            if piece:
                chunks.append(piece)
            continue

        candidate = f"{current}\n\n{paragraph}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    compacted: list[str] = []
    for chunk in chunks:
        chunk = clean_text(chunk)
        if chunk and chunk not in compacted:
            compacted.append(chunk)
    return compacted


def extract_upload(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        return clean_text("\n\n".join(pages))
    if suffix in TEXT_SUFFIXES:
        return clean_text(content.decode("utf-8", errors="ignore"))
    raise ValueError("Only PDF, TXT, Markdown files are supported.")


async def extract_web_page(url: str) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else url
    text = soup.get_text("\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return title, clean_text("\n".join(lines))
