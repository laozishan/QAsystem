from app.ingest import chunk_text, clean_text
from app.retrieval import local_embed


def test_clean_text_compacts_blank_lines():
    assert clean_text("A   B\n\n\n\nC") == "A B\n\nC"


def test_chunk_text_keeps_content():
    chunks = chunk_text("One paragraph.\n\n" + "word " * 500, max_chars=200)
    assert len(chunks) > 1
    assert "One paragraph." in chunks[0]


def test_local_embed_is_normalized():
    vector = local_embed("alpha beta beta")
    norm = sum(value * value for value in vector) ** 0.5
    assert 0.99 < norm < 1.01

