from app.services.embeddings_service import EmbeddingsService


def test_embed_texts_deterministic_fallback():
    svc = EmbeddingsService()
    # Force the hash-based fallback path so the test is hermetic regardless of
    # whether the open-clip model weights are available in the environment.
    svc._model = None
    svc._tokenizer = None

    v1 = svc.embed_texts(["hello", "world"])
    v2 = svc.embed_texts(["hello", "world"])
    assert v1 == v2
    assert len(v1) == 2
    # Fallback vectors are sized to the model's embedding dimension.
    assert all(len(vec) == svc._dim for vec in v1)
