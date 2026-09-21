from pgvector.sqlalchemy import Vector
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_engine
from app.models import Base, CorpusConfig, DocumentChunk
from app.services.embeddings import get_embedder

PIPELINE_VERSION = "page-structure-v1"


def assert_compatible(session, embedder, settings=None):
    settings = settings or get_settings()
    config = session.get(CorpusConfig, 1)
    expected = (settings.embedding_model, settings.embedding_revision, embedder.dimensions, PIPELINE_VERSION)
    if config is None or (config.model, config.revision, config.dimensions, config.pipeline_version) != expected:
        raise ValueError("Corpus/model configuration mismatch. Use a new database and reingest; do not mix embedding spaces.")


def initialize(engine=None, embedder=None, settings=None):
    engine = engine or get_engine()
    embedder = embedder or get_embedder()
    settings = settings or get_settings()
    dimensions = int(embedder.dimensions)
    if not 1 <= dimensions <= 2000:
        raise ValueError("This HNSW vector setup supports 1..2000 model-derived dimensions")
    DocumentChunk.__table__.c.embedding.type = Vector(dimensions)
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(41088001)"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(connection)
        with Session(bind=connection) as session:
            existing = session.get(CorpusConfig, 1)
            if existing is None:
                session.add(CorpusConfig(id=1, model=settings.embedding_model,
                                        revision=settings.embedding_revision, dimensions=dimensions,
                                        pipeline_version=PIPELINE_VERSION))
                session.flush()
            assert_compatible(session, embedder, settings)
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_chunks_embedding ON document_chunks "
                                "USING hnsw (embedding vector_cosine_ops)"))
    print(f"PostgreSQL + pgvector initialized; embedding dimensions={dimensions}")


if __name__ == "__main__":
    initialize()
