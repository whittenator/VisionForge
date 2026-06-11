from __future__ import annotations

import json

from sqlalchemy.types import Text, TypeDecorator


class EmbeddingVector(TypeDecorator):
    """A float-vector column: pgvector ``Vector`` on PostgreSQL, JSON text elsewhere.

    SQLite (used by tests) has no vector type, so values are JSON-encoded
    there. On PostgreSQL the pgvector type enables ANN similarity search.
    """

    impl = Text
    cache_ok = True

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector

                return dialect.type_descriptor(Vector(self.dim))
            except ImportError:
                pass
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None or dialect.name == "postgresql":
            return value
        return json.dumps([float(v) for v in value])

    def process_result_value(self, value, dialect):
        if value is None or dialect.name == "postgresql":
            return value
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None
