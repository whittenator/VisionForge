from app.services.embeddings_service import EmbeddingsService


def test_embed_texts_deterministic_fallback():
    svc = EmbeddingsService()
    v1 = svc.embed_texts(["hello", "world"])
    v2 = svc.embed_texts(["hello", "world"])
    assert v1 == v2
    assert len(v1) == 2
    assert all(len(vec) == 3 for vec in v1)
